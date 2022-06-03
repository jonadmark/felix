import json
import os
import sys
import shutil

import networkx as nx


CPU_PORT = 99
BROADCAST_MC_GRP = 99
SELECT_MC_GRP = 100
BASE_THRIFT_PORT = 9090


def main(p4prog, exp_json):
    # Prepare 'config' directory
    os.makedirs('config', exist_ok=True)
    shutil.rmtree('config')
    os.makedirs('config')

    # Load experiment definition json file
    with open(exp_json) as f:
        exp = json.load(f)
    exp['p4prog'] = p4prog
    
    # Read base parameters into variables
    slowdown = exp['slowdown']
    net = exp['network']
    n_switches = net['n_switches']
    hosts_per_switch = net['hosts_per_switch']
    switch_links = net['switch_links']
    def_link_delay = net['default_link_delay'] if 'default_link_delay' in net else None
    if def_link_delay is not None:
        def_link_delay = '{:.0f}us'.format(def_link_delay*slowdown)
    cp_loc = net['control_plane_location'] if 'control_plane_location' in net else "s1"
    def_link_bw = net['default_link_bandwidth'] if 'default_link_bandwidth' in net else None
    if def_link_bw is not None:
        def_link_bw = def_link_bw/slowdown
    queue_rate = net['queue_rate'] if 'queue_rate' in net else None
    if queue_rate is not None:
        queue_rate = queue_rate//slowdown
    queue_depth = net['queue_depth'] if 'queue_depth' in net else None
    if queue_depth is not None:
        queue_depth = queue_depth//slowdown
    edge_switches = None
    if 'edge_switches' in net:
        edge_switches = net['edge_switches']
    else:
        edge_switches = ['s{}'.format(i + 1) for i in range(n_switches)]

    # Create main config structures
    switches = {}
    hosts = {}
    links = []
    table_entries = {}
    mc_grp_entries = {}
    cli_commands = {}
    
    # Create auxiliary variables
    next_port = {}

    # Compute delay to control plane
    graph = nx.Graph()
    for i in range(n_switches):
        graph.add_node('s{}'.format(i + 1))
    for link in switch_links:
        graph.add_edge(link['u'], link['v'], weight=link['delay'])
    delay_to_cp = dict(nx.shortest_path_length(graph, cp_loc, weight='weight'))

    # Create dummy 'CPU_PORT' switch
    switches['s0'] = {
        'id': None,
        'name': 's0',
        'num': 0,
        'ip': '10.0.0.0/24',
        'mac': '01:02:04:08:16:32',
        'thrift_port': BASE_THRIFT_PORT + 0,
        'adj': {},
        'runtime_json': 'config/s0-runtime.json'
    }
    next_port['s0'] = 1
    table_entries['s0'] = []  # Drops all packets
    mc_grp_entries['s0'] = []  # Drops all packets

    # Create switches and connected hosts
    for i in range(n_switches):
        # Define name and ID for the switch
        sname = 's{}'.format(i + 1)
        sid = i
        snum = i + 1
        # Initialize rule structures
        table_entries[sname] = []
        mc_grp_entries[sname] = []
        cli_commands[sname] = ''
        # Register switch
        switches[sname] = {
            'id': sid,
            'name': sname,
            'num': snum,
            'ip': '10.0.{}.0/24'.format(snum),
            'mac': '08:00:00:00:{:02X}:00'.format(snum),
            'thrift_port': BASE_THRIFT_PORT + snum,
            'adj': {},
            'runtime_json': 'config/{}-runtime.json'.format(sname),
            'cli_input': 'config/{}-cli.txt'.format(sname)
        }
        next_port[sname] = 1
        # Add adjacency to dummy switch s0
        s0port = next_port['s0']
        next_port['s0'] = next_port['s0'] + 1
        switches['s0']['adj'][sname] = s0port
        siport = CPU_PORT
        switches[sname]['adj']['s0'] = siport
        dtcp = delay_to_cp[sname] if sname in delay_to_cp else 0
        links.append([
            's0-p{}'.format(s0port), '{}-p{}'.format(sname, siport),
            '{}us'.format(dtcp), def_link_bw
        ])
        ## Create MAC address rewriting rule
        table_entries[sname].append({
            'table': 'egress.mac_addrs',
            'match': {
                'smd.egress_port': siport
            },
            'action_name': 'egress.rewrite_mac_addrs',
            'action_params': {
                'src': switches[sname]['mac'],
                'dst': switches['s0']['mac']
            }
        })
        # Create hosts and add adjacency to them
        if sname in edge_switches:
            arp_cmds = []
            for j in range(hosts_per_switch):
                # Create host
                hnum = (snum - 1)*hosts_per_switch + j + 1
                hname = 'h{}'.format(hnum)
                hip = '10.0.{}.{}/24'.format(snum, hnum)
                hmac = '08:00:00:00:{:02X}:{:02X}'.format(snum, hnum)
                gw_ip = '10.0.{}.254'.format(snum)
                gw_mac = '08:00:00:00:{:02X}:00'.format(snum)
                hosts[hname] = {
                    'name': hname,
                    'num': hnum,
                    'ip': hip,
                    'mac': hmac,
                    'commands': [
                        'route add default gw {} dev eth0'.format(gw_ip),
                        'arp -i eth0 -s {} {}'.format(gw_ip, gw_mac)
                    ],
                    'adj': sname
                }
                arp_cmds.append('arp -i eth0 -s {} {}'.format(hip[:-3], hmac))
                # Add adjacency to host
                siport = next_port[sname]
                next_port[sname] = next_port[sname] + 1
                switches[sname]['adj'][hname] = siport
                links.append([
                    hname,  '{}-p{}'.format(sname, siport),
                    def_link_delay, def_link_bw
                ])
                ## Create MAC address rewriting rule
                table_entries[sname].append({
                    'table': 'egress.mac_addrs',
                    'match': {
                        'smd.egress_port': siport
                    },
                    'action_name': 'egress.rewrite_mac_addrs',
                    'action_params': {
                        'src': switches[sname]['mac'],
                        'dst': hosts[hname]['mac']
                    }
                })
            for j in range(hosts_per_switch):
                hname = 'h{}'.format((snum - 1)*hosts_per_switch + j + 1)
                hosts[hname]['commands'] = hosts[hname]['commands'] + arp_cmds
    
    # Build graph and add adjacency between switches
    for link in switch_links:
        uname = link['u']
        vname = link['v']
        link_bw = def_link_bw
        if 'bw' in link:
            link_bw = link['bw']/slowdown
        link_delay = def_link_delay
        if 'delay' in link:
            link_delay = '{:.0f}us'.format(link['delay']*slowdown)

        # Add adjacency between switches
        uport = next_port[uname]
        next_port[uname] = next_port[uname] + 1
        switches[uname]['adj'][vname] = uport
        vport = next_port[vname]
        next_port[vname] = next_port[vname] + 1
        switches[vname]['adj'][uname] = vport
        links.append([
            '{}-p{}'.format(uname, uport), '{}-p{}'.format(vname, vport),
            link_delay, link_bw
        ])
        ## Create MAC address rewriting rules
        table_entries[uname].append({
            'table': 'egress.mac_addrs',
            'match': {
                'smd.egress_port': uport
            },
            'action_name': 'egress.rewrite_mac_addrs',
            'action_params': {
                'src': switches[uname]['mac'],
                'dst': switches[vname]['mac']
            }
        })
        table_entries[vname].append({
            'table': 'egress.mac_addrs',
            'match': {
                'smd.egress_port': vport
            },
            'action_name': 'egress.rewrite_mac_addrs',
            'action_params': {
                'src': switches[vname]['mac'],
                'dst': switches[uname]['mac']
            }
        })
    
    # Create broadcast MC group on switches
    for sname, sinfo in switches.items():
        if sname == 's0': continue
        broadcast_mc_grp = {
            "multicast_group_id" : BROADCAST_MC_GRP,
            "replicas" : []
        }
        select_mc_grp = {
            "multicast_group_id" : SELECT_MC_GRP,
            "replicas" : []
        }
        for peer, port in sinfo['adj'].items():
            if peer[0] != 'h':
                broadcast_mc_grp['replicas'].append({
                    'egress_port': port,
                    'instance': 1
                })
                if peer != 's0':
                    select_mc_grp['replicas'].append({
                        'egress_port': port,
                        'instance': 1
                    })
        mc_grp_entries[sname].append(broadcast_mc_grp)
        mc_grp_entries[sname].append(select_mc_grp)

    # Generate topology.json configuration file
    topology_json = {
        'capture_traffic': exp['capture_traffic'],
        'run_workload': exp['run_workload'] if 'run_workload' in exp else False,
        'enable_debugger': exp['enable_debugger'] if 'enable_debugger' in exp else False,
        'slowdown': slowdown,
        'hosts': hosts,
        'switches': switches,
        'entry_installation_rate': net['entry_installation_rate'],
        'links': links,
        'failures': exp['network']['failures']
    }
    print('Creating config/topology.json', end='... ')
    with open('config/topology.json', 'w') as f:
        json.dump(topology_json, f, indent=4)
    print('done!')
    # Copy experiment definition file to config
    with open('config/experiment.json', 'w') as f:
        json.dump(exp, f, indent=4)
    
    # Generate switch configuration files
    for sname, sinfo in switches.items():
        # Runtime JSON
        if 'runtime_json' in sinfo:
            runtime_json = {
                'target': 'bmv2',
                'p4info': 'build/{}.p4.p4info.txt'.format(p4prog),
                'bmv2_json': 'build/{}.json'.format(p4prog),
                'table_entries': table_entries[sname],
                'multicast_group_entries': mc_grp_entries[sname]
            }
            print('Creating {}'.format(sinfo['runtime_json']), end='... ')
            with open(sinfo['runtime_json'], 'w') as f:
                json.dump(runtime_json, f, indent=4)
            print('done!')
        # CLI input
        if 'cli_input' in sinfo:
            cli_input = ''
            cli_input += 'register_write ingress.node_id 0 {}\n'.format(sinfo['num'])
            cli_input += 'mirroring_add {} {}\n'.format(CPU_PORT, CPU_PORT)
            if queue_rate is not None:
                cli_input += 'set_queue_rate {}\n'.format(queue_rate)
            if queue_depth is not None:
                cli_input += 'set_queue_depth {}\n'.format(queue_depth)
            cli_input += cli_commands[sname]
            print('Creating {}'.format(sinfo['cli_input']), end='... ')
            with open(sinfo['cli_input'], 'w') as f:
                f.write(cli_input)
            print('done!')


if __name__ == '__main__':
    if len(sys.argv) == 3:
        main(sys.argv[1], sys.argv[2])
    else:
        print('Usage: python3 configure.py felix|classic <experiment_json>')
        sys.exit(1)
