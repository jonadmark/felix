# Fix-it Felix
import json
import os
import queue
import signal
import sys
import time

import networkx as nx

import felix_switch
import felix_broker


def order_link(link):
    if int(link[0][1:]) < int(link[1][1:]):
        return link
    else:
        return (link[1], link[0])

def sort_links(links):
    return sorted(links, key=lambda x: (int(x[0][1:]), int(x[1][1:])))


class StateManager:
    def __init__(self):
        self.states = {'': 0}
        self.failed_links = {0: []}
    
    def add_get_state(self, failed_links):
        f_links = []
        for link in failed_links:
            f_links.append(order_link(link))
        f_links = sort_links(list(set(f_links)))
        link_names = []
        for u, v in f_links:
            link_names.append('{}-{}'.format(u, v))
        state_id = ','.join([str(x) for x in link_names])
        if state_id not in self.states:
            self.states[state_id] = len(self.states)
            self.failed_links[self.states[state_id]] = f_links
        return self.states[state_id]
    
    def get_failed_links(self, state_num):
        return self.failed_links[state_num]


def main(topology_json):
    print('Felix Routing starting up.')

    with open(topology_json) as f:
        netinfo = json.load(f)
    
    switches = netinfo['switches']
    slowdown = netinfo['slowdown']
    ei_rate = netinfo['entry_installation_rate']
    ei_delay = (1.0/ei_rate)*slowdown
    del switches['s0']

    net = {}  # net[state] = graph
    fwd = {}  # fwd[state][dst][cur_hop] = next_hops

    # Create switch interface objects and configure forwarding to hosts
    man = {}
    for sname, sinfo in switches.items():
        if sname == 's0': continue
        man[sname] = felix_switch.FelixSwitch(sinfo, script='felix')
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

    # Compute and install normal forwarding entries
    ## Create BASE_STATE graph that represents the network with no failures
    BASE_STATE = 0
    net[BASE_STATE] = nx.Graph()
    node_links = {}
    for sname, sinfo in switches.items():
        if sname == 's0': continue
        node_links[sname] = []
        net[BASE_STATE].add_node(sname)
        for peer in sinfo['adj'].keys():
            if peer != 's0' and peer[0] != 'h':
                net[BASE_STATE].add_edge(sname, peer, weight=link_delay[sname][peer])
                node_links[sname].append(order_link((sname, peer)))
    ## Run dijkstra for each switch as destination and install entries
    fwd[BASE_STATE] = {}
    for dst, dstinfo in switches.items():
        if dst == 's0': continue
        pred, _ = nx.dijkstra_predecessor_and_distance(net[BASE_STATE], dst, weight='weight')
        fwd[BASE_STATE][dst] = {}
        for cur_hop, next_hops in pred.items():
            fwd[BASE_STATE][dst][cur_hop] = sorted(next_hops)
            if len(next_hops) > 0:
                man[cur_hop].add_nrml_fwding_entry(dstinfo, next_hops)

    sttman = StateManager()
    cur_net_state = BASE_STATE
    prev_net_state = None
    failed_links = []

    TRIM_AND_CLEAR = netinfo['trim_and_clear'] if 'trim_and_clear' in netinfo else False
    visited_states = []

    ann_queue = felix_broker.announcements(switches)
    init = True
    while True:
        install_alt_entries = False
        if TRIM_AND_CLEAR and cur_net_state != prev_net_state:
            install_alt_entries = True
        elif TRIM_AND_CLEAR is False and cur_net_state not in visited_states:
            visited_states.append(cur_net_state)
            install_alt_entries = True

        if install_alt_entries:
            # Compute alternative forwarding entries
            changes = {}
            for link in net[cur_net_state].edges():
                if link in failed_links:
                    continue
                uname, vname = order_link(link)
                # Link Failure
                new_net_state = sttman.add_get_state(failed_links + [link])
                if new_net_state not in net:
                    net[new_net_state] = net[cur_net_state].copy()
                    net[new_net_state].remove_edge(uname, vname)
                    fwd[new_net_state] = {}
                    for dst, dstinfo in switches.items():
                        fwd[new_net_state][dst] = {}
                        pred, _ = nx.dijkstra_predecessor_and_distance(net[new_net_state], dst, weight='weight')
                        for cur_hop, next_hops in pred.items():
                            fwd[new_net_state][dst][cur_hop] = sorted(next_hops)
                            if len(next_hops) > 0 and fwd[new_net_state][dst][cur_hop] != fwd[BASE_STATE][dst][cur_hop]:
                                # man[cur_hop].add_alt_fwding_entry(new_net_state,
                                #                                   dstinfo,
                                #                                   next_hops)
                                if cur_hop not in changes:
                                    changes[cur_hop] = {}
                                    changes[cur_hop]['fwd'] = []
                                    changes[cur_hop]['stt'] = []
                                changes[cur_hop]['fwd'].append([new_net_state, dstinfo, next_hops])
                # Node Failure
                ## uname node
                u_lat_net_state = sttman.add_get_state(failed_links + [link] + node_links[vname])
                if u_lat_net_state not in net:
                    net[u_lat_net_state] = net[new_net_state].copy()
                    net[u_lat_net_state].remove_edges_from(node_links[vname])
                    fwd[u_lat_net_state] = {}
                    for dst, dstinfo in switches.items():
                        fwd[u_lat_net_state][dst] = {}
                        pred, _ = nx.dijkstra_predecessor_and_distance(net[u_lat_net_state], dst, weight='weight')
                        for cur_hop, next_hops in pred.items():
                            fwd[u_lat_net_state][dst][cur_hop] = sorted(next_hops)
                            if len(next_hops) > 0 and fwd[u_lat_net_state][dst][cur_hop] != fwd[BASE_STATE][dst][cur_hop]:
                                # man[cur_hop].add_alt_fwding_entry(u_lat_net_state,
                                #                                   dstinfo,
                                #                                   next_hops)
                                if cur_hop not in changes:
                                    changes[cur_hop] = {}
                                    changes[cur_hop]['fwd'] = []
                                    changes[cur_hop]['stt'] = []
                                changes[cur_hop]['fwd'].append([u_lat_net_state, dstinfo, next_hops])
                ## vname node
                v_lat_net_state = sttman.add_get_state(failed_links + [link] + node_links[uname])
                if v_lat_net_state not in net:
                    net[v_lat_net_state] = net[new_net_state].copy()
                    net[v_lat_net_state].remove_edges_from(node_links[uname])
                    fwd[v_lat_net_state] = {}
                    for dst, dstinfo in switches.items():
                        fwd[v_lat_net_state][dst] = {}
                        pred, _ = nx.dijkstra_predecessor_and_distance(net[v_lat_net_state], dst, weight='weight')
                        for cur_hop, next_hops in pred.items():
                            fwd[v_lat_net_state][dst][cur_hop] = sorted(next_hops)
                            if len(next_hops) > 0 and fwd[v_lat_net_state][dst][cur_hop] != fwd[BASE_STATE][dst][cur_hop]:
                                # man[cur_hop].add_alt_fwding_entry(v_lat_net_state,
                                #                                   dstinfo,
                                #                                   next_hops)
                                if cur_hop not in changes:
                                    changes[cur_hop] = {}
                                    changes[cur_hop]['fwd'] = []
                                    changes[cur_hop]['stt'] = []
                                changes[cur_hop]['fwd'].append([v_lat_net_state, dstinfo, next_hops])
                # State Transition
                new_net_state = sttman.add_get_state(failed_links + [link])
                if uname not in changes:
                    changes[uname] = {}
                    changes[uname]['fwd'] = []
                    changes[uname]['stt'] = []
                # man[uname].add_state_transition(cur_net_state, switches[vname],
                #                                 new_net_state, u_lat_net_state)
                changes[uname]['stt'].append([cur_net_state, switches[vname],
                                              new_net_state, u_lat_net_state])
                if vname not in changes:
                    changes[vname] = {}
                    changes[vname]['fwd'] = []
                    changes[vname]['stt'] = []
                # man[vname].add_state_transition(cur_net_state, switches[uname],
                #                                 new_net_state, v_lat_net_state)
                changes[vname]['stt'].append([cur_net_state, switches[uname],
                                              new_net_state, v_lat_net_state])
            
            # Install entries
            # if init is True:
            for cur_hop, entries in changes.items():
                prop_delay = 0 if init is True else delay_to_dp[cur_hop]
                install_delay = 0 if init is True else ei_delay
                felix_broker.send_entry_updates(man[cur_hop], prop_delay,
                                                install_delay, entries)
            init = False

        print('=> Current network state is', cur_net_state)
        print('Current failed links set is', failed_links)

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

        if ann.new_net_state == 0:
            # Update the network state
            if cur_net_state != 0:
                # IF TRIM_AND_CLEAR IS TRUE
                prev_net_state = None
                # IF TRIM_AND_CLEAR IS FALSE
                visited_states = []
                #
                failed_links = []
                cur_net_state = BASE_STATE
                print('New network state is', cur_net_state)
                print('No links are failed')
                net = {BASE_STATE: net[BASE_STATE]}
                fwd = {BASE_STATE: fwd[BASE_STATE]}
                # Clear alternative forwarding and state transition tables
                for sname in switches.keys():
                    if sname == 's0': continue
                    man[sname].clear_alt_fwding_table()
                    man[sname].clear_state_transition_table()
            else:
                print('Replicated announcement for the current net state. Nothing to do.')
        elif ann.new_net_state > 0:
            # Update the network state
            prev_net_state = cur_net_state
            new_net_state = ann.new_net_state
            if new_net_state != cur_net_state:
                cur_net_state = new_net_state
                print('New network state is', cur_net_state)
                failed_links = sttman.get_failed_links(new_net_state)
                print('New failed links set is', failed_links)
                if TRIM_AND_CLEAR:
                    # Trim the alternative forwarding table
                    # and clear the state transition table
                    for sname in switches.keys():
                        if sname == 's0': continue
                        man[sname].trim_alt_fwding_table([prev_net_state, cur_net_state])
                        man[sname].clear_state_transition_table()
            else:
                print('Replicated announcement for the current net state. Nothing to do.')
            print('Latent failed links set is', sttman.get_failed_links(ann.latent_net_state))
        
        print()


if __name__ == '__main__':
    if len(sys.argv) > 1:
        main(sys.argv[1])
    else:
        print('Usage: python3 felix_routing.py <topology_json>')
        print('Using default file... config/topology.json')
        main('config/topology.json')