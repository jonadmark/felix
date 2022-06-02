# To add a new cell, type '# %%'
# To add a new markdown cell, type '# %% [markdown]'
# %%
# from IPython import get_ipython

# %% [markdown]
# # Parameters

# %%
dataset_metatada = './networks/metadata.json'
n_workers=30
opt = 'selected'
dvs = {
    "selected": {
        "TopologyZoo": ["Bellcanada", "Cogentco"],
        "DEFO": ["rf1239_real_hard"],
        "FatTree": ["FatTree8", "FatTree16", "FatTree32"]
    }
}
dataset_view = dvs[opt] if opt in dvs else None

# %% [markdown]
# # Module Imports

# %%
import collections
import copy
import json
import math
import random
import time

from multiprocessing import Pool
from heapq import heappush, heappop

import networkx as nx
import numpy as np
import pandas as pd


# %%
# MATPLOTLIB AND SEABORN
import matplotlib.pylab as pylab
from matplotlib.patches import Rectangle
from matplotlib.ticker import (MultipleLocator, FormatStrFormatter, AutoMinorLocator)

# get_ipython().run_line_magic('matplotlib', 'inline')

pylab.rcParams['font.size'] = 24
pylab.rcParams['figure.figsize'] = [3*x for x in [3.52, 2.64]]
pylab.rcParams['figure.dpi'] = 100
pylab.rcParams['errorbar.capsize'] = 3
pylab.rcParams['legend.fontsize'] = 12
pylab.rcParams['lines.linewidth'] = 2

gridcolor = '#bbbbbb'

zvalue = 2.576  # 99%

# %% [markdown]
# # Processing Functions

# %%
class ForwardingTactic:
    __ids = {"": 0}

    def __init__(self, id, n_entries, nexthops, prevhops, reachability, dist, n_transition_entries=None, failure_set=None):
        self.id = id
        self.n_entries = n_entries
        self.total_n_entries = int(n_entries.sum())
        self.nexthops = nexthops
        self.prevhops = prevhops
        self.reachability = reachability
        self.dist = dist
        self.n_transition_entries = n_transition_entries
        self.failure_set = failure_set

        self.parent_a = 0
        self.parent_b = 0
        self.savings = 0
    
    def set_parents(self, parent_a, parent_b, savings):
        self.parent_a = parent_a
        self.parent_b = parent_b
        self.savings = savings
    
    @classmethod
    def get_id(cls, failure_set):
        # fs = '.'.join([str(x) for x in sorted(failure_set)])  # str-based
        fs = tuple(failure_set)  # tuple-based
        if fs not in cls.__ids:
            cls.__ids[fs] = len(cls.__ids)
        return cls.__ids[fs]

# %%
def cnft(nm, graph, dst):
    n = nm['n_nodes']
    n_dst = len(nm['edge_switches']) if 'edge_switches' in nm else n

    n_entries = np.zeros(n, dtype=np.uint)  # [cur] -> number of forwarding entries in cur
    nexthops = {}  # [cur] -> list of next hops from cur to dst
    prevhops = {}  # [cur] -> list of previous hops from cur to dst
    reachability = np.zeros(n_dst, dtype=np.bool_)  # [src] -> reachability from src to dst
    dist = np.empty(n)  # [cur] -> distance from cur to dst
    dist.fill(math.inf)
    dist[dst] = 0
    visited = np.zeros(n, dtype=np.bool_)
    
    queue = [(0, dst)]
    while queue:
        _, u = heappop(queue)
        if visited[u]:
            continue
        visited[u] = 1
        if u < n_dst:
            reachability[u] = 1
        if len(nexthops) > 0:
            n_entries[u] = n_entries[u] + 1
        prevhops[u] = set()
        for v, md in graph.adj[u].items():
            dist_via_u = dist[u] + md['w']
            distdiff = dist_via_u - dist[v]
            if distdiff < 0:
                nexthops[v] = set([u])
                dist[v] = dist_via_u
                prevhops[u].add(v)
                heappush(queue, (dist_via_u, v))
            elif distdiff == 0:
                nexthops[v].add(u)
                prevhops[u].add(v)

    return (n_entries, nexthops, prevhops, reachability, dist)

# %%
def cnft_worker(nm, graph, worker_id, n_workers):
    n = nm['n_nodes']
    n_dst = len(nm['edge_switches']) if 'edge_switches' in nm else n

    n_entries = np.zeros(n, dtype=np.uint)  # [cur] -> number of forwarding entries in cur
    nexthops = {}  # [dst][cur] -> list of next hops from cur to dst
    prevhops = {}  # [dst][cur] -> list of previous hops from cur to dst
    reachability = np.zeros((n_dst, n_dst), dtype=np.bool_)  # [dst][src] -> reachability from src to dst
    dist = {}  # [dst][cur] -> distance from cur to dst

    for i, dst in enumerate(range(n_dst)):
        if (i % n_workers) == worker_id:
            results = cnft(nm, graph, dst)
            n_entries = n_entries + results[0]
            nexthops[dst] = results[1]
            prevhops[dst] = results[2]
            reachability[dst] = results[3]
            dist[dst] = results[4]
    
    return (n_entries, nexthops, prevhops, reachability, dist)


def cnft_iface(nm, graph, n_workers):
    n = nm['n_nodes']
    n_dst = len(nm['edge_switches']) if 'edge_switches' in nm else n

    n_entries = np.zeros(n, dtype=np.uint)  # [cur] -> number of forwarding entries in cur
    nexthops = {}  # [dst][cur] -> list of next hops from cur to dst
    prevhops = {}  # [dst][cur] -> list of previous hops from cur to dst
    reachability = np.zeros((n_dst, n_dst), dtype=np.bool_)  # [dst][src] -> reachability from src to dst
    dist = {}  # [dst][cur] -> distance from cur to dst

    worker_arguments = ((nm, graph, i, n_workers) for i in range(n_workers))
    with Pool(processes=n_workers) as pool:
        workers_results = pool.starmap(cnft_worker, worker_arguments)
    
    for worker_results in workers_results:
        n_entries = n_entries + worker_results[0]
        nexthops.update(worker_results[1])
        prevhops.update(worker_results[2])
        reachability = reachability + worker_results[3]
        dist.update(worker_results[4])
    
    return ForwardingTactic(0, n_entries, nexthops, prevhops, reachability, dist)



# %%
def node(u):
    if u is None:
        return None
    return u + 1

def hlink(l):
    if l is None:
        return None
    return (node(l[0]), node(l[1]))

def caft(nm, graph, nft, ftid, failure_set):
    debug = False

    # print(f"Failure Set: {[hlink(x) for x in failure_set]}")

    n = nm['n_nodes']
    n_dst = len(nm['edge_switches']) if 'edge_switches' in nm else n
    # n_dst = n

    nexthops = {}  # [dst][cur] -> list of next hops from cur to dst
    # prevhops = {}  # [dst][cur] -> list of previous hops from cur to dst
    n_entries = np.zeros(n, dtype=np.uint)  # [cur] -> number of forwarding entries in cur
    n_transition_entries = np.zeros(n, dtype=np.uint)  # [cur] -> number of forwarding entries in cur
    reachability = copy.deepcopy(nft.reachability)  # [dst][src] -> reachability from src to dst
    dist = copy.deepcopy(nft.dist)  # [dst][cur] -> distance from cur to dst

    cur_graph = graph.copy()
    for (u, v) in failure_set:
        cur_graph.remove_edge(u, v)
        n_transition_entries[u] = n_transition_entries[u] + 1
        n_transition_entries[v] = n_transition_entries[v] + 1

    for dst in range(n_dst):
        # print(f"Destination: {node(dst)}")
        # print(f"Distance: {dist[dst]}")
        recompute = []
        visited = np.ones(n, dtype=np.bool_)
        # Marks all the nodes that will have to have nexthops recomputed
        for (u, v) in failure_set:
            if debug: print(f"Failed Element: {(node(u), node(v))}")
            distdiff = nft.dist[dst][u] - nft.dist[dst][v]
            
            # if both nodes are on the same level,
            if distdiff == 0:
                # then there is no dependency and no need to change forwarding
                continue
            
            # make sure u is always the node further away from dst
            if distdiff < 0:
                u, v = v, u
            
            # if we have not dealt with u already (set dist to infinity)
            # and link (u, v) is in the SPDAG to dst
            if dist[dst][u] != math.inf and v in nft.nexthops[dst][u]:
                # a change in forwarding is definitely needed
                # perform a reverse BFS on the graph
                # print(f"Setting dist[{dst}][{u}] to math.inf.")
                dist[dst][u] = math.inf
                queue = collections.deque([u])
                while queue:
                    u = queue.popleft()
                    # print(f"Node {node(u)} is affected!")
                    # add node to list of recompute (partial Dijkstra)
                    recompute.append(u)
                    # update reachability temporarily
                    if u < n_dst:
                        reachability[dst][u] = 0
                    # mark as not visited
                    visited[u] = 0
                    # add original prevhops as next to be updated
                    for v in nft.prevhops[dst][u]:
                        if dist[dst][v] != math.inf:
                            # print(f"Setting dist[{dst}][{v}] to math.inf.")
                            dist[dst][v] = math.inf
                            queue.append(v)
        
        # If there are nodes that need to have their nextgops recomputed
        if recompute:
            nexthops[dst] = {}
            # prevhops[dst] = {}

            # Build initial priority queue for Dijkstra
            heapq = []
            # print(f"Preparing to recompute:")
            for u in recompute:
                # compute the shortest known available path length from u to dst
                # and the appropriate nexthops
                min_dist = math.inf
                nhs = set()
                for v, md in cur_graph.adj[u].items():
                    if dist[dst][v] != math.inf:
                        dist_via_v = dist[dst][v] + md['w']
                        distdiff = dist_via_v - min_dist
                        if distdiff < 0:
                            min_dist = dist_via_v
                            nhs = set([v])
                        elif distdiff == 0:
                            nhs.add(v)
                # update dist and nexthops variables
                # print(f"Setting dist[{dst}][{u}] to {min_dist}.")
                dist[dst][u] = min_dist
                nexthops[dst][u] = nhs
                # print(f"Node: {node(u)} => {[node(x) for x in nhs]} ({min_dist})")
                # add to priority queue only if cost is not infinity
                if min_dist != math.inf:
                    heappush(heapq, (min_dist, u))
            
            # Recompute shortest paths for the affected nodes
            while heapq:
                _, u = heappop(heapq)
                # print(end=f"Extracted node {node(u)} from priority queue. ")
                # update reachability
                if u < n_dst:
                    reachability[dst][u] = 1
                # update visited
                visited[u] = 1
                # check if alternative forwarding entry is necessary
                ## prefered version
                if nexthops[dst][u] and not nexthops[dst][u].issuperset(nft.nexthops[dst][u]):
                    n_entries[u] = n_entries[u] + 1
                ## simpler version
                # if nexthops[dst][u] != nft.nexthops[dst][u]:
                #     n_entries[u] = n_entries[u] + 1
                # print(f"Best path has cost {dist[dst][u]} via {[node(x) for x in nexthops[dst][u]]}.")
                # relax path costs to neighbors
                for v, md in cur_graph.adj[u].items():
                    # print(f"Checking neighbor node {node(v)}, current cost is {dist[dst][v]}.")
                    # if best path to v hasn't already been found
                    if not visited[v]:
                        dist_via_u = dist[dst][u] + md['w']
                        distdiff = dist_via_u - dist[dst][v]
                        # if path from v through u is (one of) the best
                        if distdiff < 0:
                            # update dist and replace nexthops
                            # print(f"Setting dist[{dst}][{u}] to {dist_via_u}.")
                            dist[dst][v] = dist_via_u
                            nexthops[dst][v] = set([u])
                            # update cost on the priority queue
                            heappush(heapq, (dist_via_u, v))
                        elif distdiff == 0:
                            # update nexthops
                            nexthops[dst][v].add(u)
    
    if False:
        print(f"### Alternative Forwarding for Failure Set: {[(u + 1, v + 1) for (u, v) in failure_set]}")
        # print(f"n_entries: {n_entries}")
        # for dst in debug_destinations:
        for dst in range(n_dst):
            print(f"## Destination: {dst + 1}")
            print(end=f"# Next Hops:")
            for cur in range(n):
                if cur == dst: continue
                if nexthops[dst][cur] != nft.nexthops[dst][cur]:
                    print(end=f" {cur + 1}=>{np.array(list(nexthops[dst][cur])) + 1}")
            print()
            # print(f"# Prev Hops:")
            # for cur, phs in sorted(prevhops[dst].items()):
            #     print(f"{cur + 1}: {np.array(list(phs)) + 1}")
            # print(f"Distance: {dist[dst]}")

    # return ForwardingTactic(ftid, n_entries, nexthops, None, reachability, dist, n_transition_entries, failure_set)
    return ForwardingTactic(ftid, n_entries, None, None, reachability, dist, n_transition_entries, failure_set)

# %%
def caft_worker(nm, graph, nft, worker_id, n_workers):
    n = len(graph.nodes)
    m = len(graph.edges)

    # fts = {}

    worker_n_entries = np.zeros(n)
    worker_n_transition_entries = np.zeros(n)
    n_fs_prepd = 0
    for i, link in enumerate(graph.edges):
        if (i % n_workers) == worker_id:
            ftid = i + 1
            aft = caft(nm, graph, nft, ftid, [link])
            worker_n_entries = worker_n_entries + aft.n_entries
            worker_n_transition_entries = worker_n_transition_entries + aft.n_transition_entries
            # fts[ftid] = aft
            # print(end=".", flush=True)
    for i, node in enumerate(graph.nodes):
        if ((m + i) % n_workers) == worker_id:
            ftid = m + i + 1
            aft = caft(nm, graph, nft, ftid, [(node, v) for v in graph.adj[node]])
            worker_n_entries = worker_n_entries + aft.n_entries
            worker_n_transition_entries = worker_n_transition_entries + aft.n_transition_entries
            # fts[ftid] = aft
            # print(end=".", flush=True)
    return (None, worker_n_entries, worker_n_transition_entries)


# %%
def n_bits(x):
    return int(math.ceil(math.log2(x)))

def evaluate(nm, graph, n_workers):
    n = len(graph.nodes)
    m = len(graph.edges)
    n_fts = 1 + n + m

    print(end=f"  Compute normal forwarding entries", flush=True)
    # fts = {}
    fts = [None for _ in range(n_fts)]
    ts = time.time()
    fts[0] = cnft_iface(nm, graph, n_workers)
    normal_time = round(time.time() - ts, 6)
    print(f"\r  Normal: time={normal_time:.6f}s n_entries={fts[0].total_n_entries}", flush=True)

    # Register ForwardingTactics for each single link/node failure scenario
    for link in graph.edges:
        ForwardingTactic.get_id([link])
    for node in graph.nodes:
        ForwardingTactic.get_id([(node, v) for v in graph.adj[node]])

    total_n_alt_entries = 0
    global_n_entries = np.zeros(len(graph.nodes))
    global_n_transition_entries = np.zeros(len(graph.nodes))
    ts = time.time()
    worker_arguments = ((nm, graph, fts[0], i, n_workers) for i in range(n_workers))
    with Pool(processes=n_workers) as pool:
        workers_results = pool.starmap(caft_worker, worker_arguments)
    alt_time = round(time.time() - ts, 6)
    for _, worker_n_entries, worker_n_transition_entries in workers_results:
        global_n_entries = global_n_entries + worker_n_entries
        global_n_transition_entries = global_n_transition_entries + worker_n_transition_entries
    total_n_alt_entries = int(global_n_entries.sum())
    alt_max = int(global_n_entries.max())
    print(f"  Alternative: time={alt_time:.6f}s n_entries={total_n_alt_entries} n_max_entries={alt_max}", flush=True)

    n_opposite_entries = np.zeros(n)
    for u in graph.nodes:
        n_opposite_entries[u] = len(graph.adj[u])

    # Build metadata dict
    port_bitwidth = 9
    md = {
        'port_bitwidth': port_bitwidth,
        'nrml_fwding_table_args_bitwidth': port_bitwidth + n_bits(n),
        'alt_fwding_table_key_bitwidth': n_bits(n_fts) + n_bits(n),
        'alt_fwding_table_args_bitwidth': port_bitwidth,
        'opposite_table_key_bitwidth': port_bitwidth,
        'opposite_table_args_bitwidth': n_bits(n),
        'state_transition_table_key_bitwidth': n_bits(n_fts) + n_bits(n),
        'state_transition_table_args_bitwidth': 2*n_bits(n_fts),
        "n_nodes": n,
        "n_edges": m,
        "n_fts": len(fts),
        "ttc_normal_forwarding": normal_time,
        "ttc_alt_forwarding": alt_time,
    }
    # Build summary dataframe
    df = pd.DataFrame()
    df['n_nrml_fwding_table_entries'] = fts[0].n_entries
    df['n_alt_fwding_table_entries'] = global_n_entries
    df['n_opposite_table_entries'] = n_opposite_entries
    df['n_state_transition_table_entries'] = global_n_transition_entries
    #
    return md, df

# %% [markdown]
# ## Process Network

# %%
def proc_network(nm, n_workers):
    graph = nx.Graph()
    for node in nm['nodes']:
        graph.add_node(node['id'], label=node['label'])
    for edge in nm['edges']:
        graph.add_edge(edge['src'], edge['dst'], w=edge['delay'])
        graph.add_edge(edge['dst'], edge['src'], w=edge['delay'])

    result = evaluate(nm, graph, n_workers)
    return result

# %% [markdown]
# ## Main Loop

# %%
def main_loop(opt, dm, n_workers):
    base_dir = dm['base_directory']
    datasets = dm['datasets']

    df = None


    for ds in datasets:
        print(f"Dataset={ds['name']}")
        for nn in ds['networks']:
            print(f" Network: {nn}")
            with open(f"{base_dir}/{ds['directory']}/{nn}.graph.json") as f:
                nm = json.load(f)
            cmd, cdf = proc_network(nm, n_workers)
            # print(cmd)
            # print(cdf)
            with open(f"./results/routing/summary/{ds['name']}-{nn}.json", "w") as f:
                json.dump(cmd, f, indent=4)
            cdf.to_csv(f"./results/routing/summary/{ds['name']}-{nn}.csv")
            print()
    return df

# %% [markdown]
# # Compute Data

# %%
# %%time

# Open full metadata
if __name__ == "__main__":
    with open(dataset_metatada) as f:
        dm = json.load(f)

    # Apply view
    if dataset_view is not None:
        datasets = []
        for ds in dm['datasets']:
            if ds['name'] in dataset_view.keys():
                ds['networks'] = dataset_view[ds['name']]
                datasets.append(ds)
        dm['datasets'] = datasets

    # Run main loop
    df = main_loop(opt, dm, n_workers=n_workers)
    print(df)
