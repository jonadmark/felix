# Wreck-it Ralph
import json
import random
import sys
import time

import networkx as nx

import felix_switch


def main(p4prog, topology_json):
    print('Ralph starting up.')
    
    with open(topology_json) as f:
        net = json.load(f)
    
    slowdown = net['slowdown']

    switches = {}
    n_switches = len(net['switches']) - 1
    for sname, sinfo in net['switches'].items():
        if sname == 's0': continue
        if p4prog == 'felix':
            switches[sname] = felix_switch.FelixSwitch(sinfo, script='ralph')
        elif p4prog == 'classic':
            switches[sname] = classic_switch.ClassicSwitch(
                sinfo, script='ralph')
        switches[sname].set_all_interfaces_up()

    lds = {}
    for link_def in net['links']:
        src, dst, ld = link_def[0], link_def[1], link_def[2]
        if src[0] == 's':
            src = src.split('-')[0]
        if dst[0] == 's':
            dst = dst.split('-')[0]
        if src not in lds:
            lds[src] = {}
        if dst not in lds:
            lds[dst] = {}
        lds[src][dst] = lds[dst][src] = float(ld[:-2])/1e6

    failures = net['failures']

    failed_links = []
    failed_nodes = []

    for failure in failures:
        delay = failure['delay']*slowdown
        ftype = failure['type']
        elmnt = failure['element'] if 'element' in failure else None
        
        print('Sleeping for {} seconds'.format(delay))
        time.sleep(delay)

        if ftype == 'reset':
            failed_links = []
            failed_nodes = []
            for sname, sw in switches.items():
                sw.reset_all_interfaces_up()
        elif ftype == 'random':
            print('Failure type is random.', end=' ')
            if elmnt is None:
                ran = random.uniform(0, 100)
                if ran < 70.0:
                    elmnt = 'link'
                else:
                    elmnt = 'node'
            
            if elmnt == 'link':
                ftype = 'link'
                found = False
                while not found:
                    uname, vname = random.choice(net['links'])
                    if uname != 's0' and uname[0] != 'h' and vname != 's0' and vname[0] != 'h' and (uname, vname) not in failed_links:
                        found = True
                elmnt = [uname, vname]
            elif elmnt == 'node':
                ftype = 'node'
                found = False
                while not found:
                    uname = random.randint(1, n_switches)
                    if uname not in failed_nodes:
                        found = True
                elmnt = uname

        if ftype == 'link':
            # Link failure
            uname, vname = elmnt
            if (uname, vname) not in failed_links:
                print('Failing link ({}, {}).'.format(uname, vname))
                switches[uname].set_interface_down(vname)
                switches[vname].set_interface_down(uname)
                # time.sleep(lds[uname][vname])
                switches[uname].set_link_down(vname)
                switches[vname].set_link_down(uname)
                failed_links.append((uname, vname))
                failed_links.append((vname, uname))
            else:
                print('Link ({}, {}) is already failed. Nothing to do.'.format(uname, vname))
        elif ftype == 'node':
            # Node failure
            uname = elmnt
            if uname not in failed_nodes:
                print('Failing node {}.'.format(uname))
                switches[uname].set_switch_down()
                failed_nodes.append(uname)
                for vname in switches[uname].adj.keys():
                    if vname != 's0' and vname[0] != 'h':
                        switches[vname].set_interface_down(uname)
                        # time.sleep(lds[vname][uname])
                        switches[vname].set_link_down(uname)
                        failed_links.append((uname, vname))
                        failed_links.append((vname, uname))
            else:
                print('Node {} is already failed. Nothing to do.'.format(uname))


if __name__ == '__main__':
    if len(sys.argv) == 3:
        main(sys.argv[1], sys.argv[2])
    else:
        print('Usage: python3 ralph.py felix|classic <topology_json>')
        print('Using default experiment... felix')
        print('Using default file... config/topology.json')
        main('felix', 'config/topology.json')
