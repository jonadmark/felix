import json
import os
import queue
import signal
import sys
import time

import networkx as nx

import classic_broker
import classic_switch


def bitwise_not(n, numbits=32):
    return (1 << numbits) - 1 - n


def order_link(link):
    if int(link[0][1:]) < int(link[1][1:]):
        return link
    else:
        return (link[1], link[0])


def sort_links(links):
    return sorted(links, key=lambda x: (int(x[0][1:]), int(x[1][1:])))


def main(topology_json):
    print('Classic Routing starting up.')

    with open(topology_json) as f:
        netinfo = json.load(f)

    switches = netinfo['switches']
    slowdown = netinfo['slowdown']
    ei_rate = netinfo['entry_installation_rate']
    ei_delay = (1.0/ei_rate)*slowdown
    del switches['s0']

    # Create switch interface objects and configure forwarding to hosts
    man = {}
    for sname, sinfo in switches.items():
        if sname == 's0':
            continue
        man[sname] = classic_switch.ClassicSwitch(sinfo, script='classic')
        for peer in sinfo['adj'].keys():
            if peer[0] == 'h':
                man[sname].add_nrml_fwding_entry_host(netinfo['hosts'][peer])
        man[sname].set_all_interfaces_up()

    # Get control plane communication delays
    delay_to_dp = {}
    link_delay = {}
    for link in netinfo['links']:
        if link[0][:2] == 's0':
            delay_to_dp[link[1].split('-')[0]] = int(link[2][:-2])*slowdown/1e6
        if link[0][0] != 'h' and link[1][0] != 'h':
            u = link[0].split('-')[0]
            v = link[1].split('-')[0]
            d = int(link[2][:-2])
            if u not in link_delay:
                link_delay[u] = {}
            if v not in link_delay:
                link_delay[v] = {}
            link_delay[u][v] = d
            link_delay[v][u] = d

    # Create graph to represent the current network state
    net = nx.Graph()
    fwd = {}  # fwd[dst][cur_hop] = next_hop
    node_links = {}
    port_to_peer = {}
    for sname, sinfo in switches.items():
        if sname == 's0':
            continue
        node_links[sname] = []
        net.add_node(sname)
        port_to_peer[sname] = {}
        for peer, port in sinfo['adj'].items():
            port_to_peer[sname][port] = peer
            if peer != 's0' and peer[0] != 'h':
                net.add_edge(sname, peer, weight=link_delay[sname][peer])
                node_links[sname].append(order_link((sname, peer)))
    
    failed_links = set()
    ann_queue = classic_broker.announcements(switches)
    changed = True
    init = True
    while True:
        if changed is True:
            ## Run dijkstra for each switch as destination
            print('Computing (new) forwarding entries.')
            st = time.time()
            changes = {}
            for dst, dstinfo in switches.items():
                if dst == 's0':
                    continue
                pred, _ = nx.dijkstra_predecessor_and_distance(net, dst, weight='weight')
                if dst not in fwd:
                    fwd[dst] = {}
                for cur_hop, next_hops in pred.items():
                    o_next_hops = sorted(next_hops)
                    if cur_hop not in fwd[dst]:
                        fwd[dst][cur_hop] = []
                    if len(o_next_hops) > 0 and o_next_hops != fwd[dst][cur_hop]:
                        if cur_hop not in changes:
                            changes[cur_hop] = []
                        changes[cur_hop].append([dstinfo, o_next_hops])
                        fwd[dst][cur_hop] = o_next_hops
                # for cur_hop in switches.keys():
                #     if cur_hop not in pred:
                #         print('{} will drop packets to {}'.format(cur_hop, dst))
                #         if cur_hop not in changes:
                #             changes[cur_hop] = []
                #         changes[cur_hop].append([dstinfo, ['drop']])
                #         fwd[dst][cur_hop] = ['drop']
            et = time.time()
            # Simulate computation delay
            # if init is False:
                # time_to_sleep = (et - st)*1e6*slowdown - (et - st)
                # print('Sleeping for {:.3f} seconds.'.format(time_to_sleep))
                # time.sleep(time_to_sleep)
            # Install entries
            print('Installing/updating forwarding entries.')
            for cur_hop, entries in changes.items():
                prop_delay = 0 if init is True else delay_to_dp[cur_hop]
                install_delay = 0 if init is True else ei_delay
                classic_broker.send_entry_updates(man[cur_hop], prop_delay,
                                                  install_delay, entries)
            init = False

        changed = False

        print('=> Current failed links set is', failed_links)

        print('Waiting for a new annoucement', end='.')
        ann = None
        while ann is None:
            print(end='.')
            try:
                ann = ann_queue.get(timeout=1)
            except queue.Empty:
                pass
            with open('/tmp/felix_routing_exit_flag') as f:
                if f.read() == '1':
                    print('Exiting!')
                    sys.exit(0)
        print('\nAnnouncement received!', ann)

        loc_state_change = ann.prev_loc_state & (bitwise_not(ann.new_loc_state))
        u = ann.announcer
        for bit in range(32):
            if (1<<bit) & loc_state_change:
                v = port_to_peer[u][bit + 1]
                if v in net.adj[u]:
                    changed = True
                    net.remove_edge(u, v)
                    failed_links.add(order_link((u, v)))


if __name__ == '__main__':
    if len(sys.argv) > 1:
        main(sys.argv[1])
    else:
        print('Usage: python3 classic_routing.py <topology_json>')
        print('Using default file... config/topology.json')
        main('config/topology.json')
