import json
import math

import networkx as nx

base_dir = '.'

# for n_ports in [4, 8, 12, 24, 32, 48, 64, 256]:
for n_ports in [16]:
    n_ports2 = int(n_ports/2)
    n_pods = n_ports
    n_tor_sw = n_agg_sw = int(n_pods*(n_ports/2))
    n_hosts = n_tor_sw*n_ports2
    n_tor_pp = n_agg_pp = int(n_tor_sw/n_pods)
    n_core_sw = int(pow(n_ports/2, 2))

    debug = False

    graph = nx.Graph()
    # TOR to AGG
    n_tor_agg_edges = 0
    for i in range(n_tor_sw):
        u = i
        for j in range(n_ports2):
            v = n_tor_sw + math.floor(i/n_tor_pp)*n_tor_pp + j
            if debug:
                print(f"s{u + 1}-s{v + 1}")
            graph.add_edge(u, v, weight=50)
            n_tor_agg_edges = n_tor_agg_edges + 1

    # AGG to CORE
    n_agg_core_edges = 0
    for i in range(n_agg_sw):
        u = n_tor_sw + i
        for j in range(n_ports2):
            v = n_tor_sw + n_agg_sw + n_ports2*j + (i%n_agg_pp)
            if debug:
                print(f"s{u + 1}-s{v + 1}")
            graph.add_edge(u, v, weight=100)
            n_agg_core_edges = n_agg_core_edges + 1

    graph_dict = {
        'type': 'fattree',
        'n_nodes': len(graph.nodes),
        'n_ports': n_ports,
        'n_pods': n_pods,
        'n_tor_nodes': n_tor_sw,
        'n_tor_nodes_per_pod': n_tor_pp,
        'n_agg_nodes': n_agg_sw,
        'n_agg_nodes_per_pod': n_agg_pp,
        'n_core_nodes': n_core_sw,
        'n_edges': len(graph.edges),
        'n_tor_agg_edges': n_tor_agg_edges,
        'n_agg_core_edges': n_agg_core_edges,
        'n_hosts': n_hosts,
        'edge_switches': list(range(n_tor_sw))
    }
    graph_dict['nodes'] = []
    graph_dict['edges'] = []
    nid = 0
    for node in graph.nodes:
        graph_dict['nodes'].append({
            'id': node,
            'label': f"s{node + 1}",
        })
        for peer in graph.adj[node]:
            if node < peer:
                graph_dict['edges'].append({
                    'id': nid,
                    'label': f"edge_{nid}",
                    "src": node,
                    "dst": peer,
                    "delay": graph.adj[node][peer]['weight'],
                    "weight": graph.adj[node][peer]['weight']
                })
                nid = nid + 1
    
    with open(f"{base_dir}/FatTree{n_ports}.graph.json", 'w') as f:
        json.dump(graph_dict, f, indent=4)
