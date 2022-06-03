import json
import math
import sys

import networkx as nx


def order(u):
    if u[0] == 'h':
        return int(u[1:])
    return 1000000 + int(u[1:])

def swarn(p_value):
    if p_value < 50.0:
        return ''
    else:
        return ' <' + '==='*int(math.floor((p_value - 40)/10))


def main(exp_json):
    # Load experiment definition json file
    with open(exp_json) as f:
        exp = json.load(f)
    
    net = exp['network']
    slowdown = exp['slowdown']
    link_bw = round(net['default_link_bandwidth']/slowdown, 2)
    failures = [{}] + net['failures']

    print('link bandwidth:', link_bw, 'Mbps')

    wl = exp['workload']
    multiplier = wl['multiplier']

    graph = nx.Graph()
    for link in net['switch_links']:
        graph.add_edge(link['u'], link['v'], weight=link['delay'])
    
    for sid in range(net['n_switches']):
        snum = sid + 1
        sname = 's{}'.format(snum)
        for j in range(net['hosts_per_switch']):
            hnum = (snum - 1)*net['hosts_per_switch'] + j + 1
            hname = 'h{}'.format(hnum)
            graph.add_edge(hname, sname)
    
    for f in failures:
        if f == dict():
            print('\n####################')
            print('# Normal Operation #')
            print('####################')
        else:
            ftype = f['type']
            felem = f['element']
            if ftype == 'link':
                print('\n########################')
                print('# Fail Link ({:>3s}, {:>3s}) #'.format(felem[0], felem[1]))
                print('########################')
                graph.remove_edge(felem[0], felem[1])
            elif ftype == 'node':
                print('\n########################')
                print('# Fail Node {:>3s}        #'.format(felem))
                print('########################')
                graph.remove_node(felem)
        util = {}
        for demand in wl['demands']:
            debug = False
            # if demand['src'] == 'h8':
            #     debug = True
            src = demand['src']
            dst = demand['dst']
            if debug: print(f'src: {src} dst: {dst}')

            try:
                spaths = list(nx.all_shortest_paths(graph, src, dst, weight='weight'))
                if debug:
                    print(f'paths: {spaths}')

                multipath = True
                if multipath:
                    nrate = ((demand['rate']/slowdown)*multiplier)/len(spaths)
                else:
                    nrate = ((demand['rate']/slowdown)*multiplier)
                if debug: print(f'nrate: {nrate}')

                for spath in spaths:
                    if debug: print(f'cur_path: {spath}')
                    for i in range(len(spath) - 1):
                        u = spath[i]
                        v = spath[i + 1]
                        if debug: print(f'u: {u} v: {v}')
                        if u not in util:
                            util[u] = {}
                        if v not in util[u]:
                            util[u][v] = 0
                        util[u][v] = util[u][v] + nrate
                    if not multipath:
                        break
            except:
                pass

        max_link_util = 0
        max_node_util = 0

        for u in sorted(util.keys(), key=order):
            acum_util = 0
            for v in sorted(util[u].keys(), key=order):
                putil = util[u][v]*100/link_bw
                max_link_util = max(max_link_util, putil)
                acum_util = acum_util + util[u][v]
                print('{:>3s} {:>3s} {:6.2f}% {:6.2f} Mbps{}'.format(u, v, putil, util[u][v], swarn(putil)))
            pacum_util = acum_util*100/(link_bw*5)
            max_node_util = max(max_node_util, pacum_util)
            if u[0] != 'h':
                print('{:>3s} === {:6.2f}% {:6.2f} Mbps{}'.format(u, pacum_util, acum_util, swarn(pacum_util)))
        print(f'max_link_util: {max_link_util:.2f}%')
        print(f'max_node_util: {max_node_util:.2f}%')


if __name__ == '__main__':
    if len(sys.argv) == 2:
        main(sys.argv[1])
    else:
        print('Usage: python3 configure.py <experiment_json>')
        sys.exit(1)
