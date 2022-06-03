"""Analyze Logs.

Usage:
    analyze_logs.py <exp_json> <bwl_json> <logs_dir>
"""
import json

import pandas as pd

from docopt import docopt


def main(exp_json, bwl_json, logs_dir, quiet=False):
    # Load main experiment definition json file
    with open(exp_json) as f:
        exp = json.load(f)

    # Read base parameters into variables
    n_switches = exp['network']['n_switches']
    hosts_per_switch = exp['network']['hosts_per_switch']
    if 'edge_switches' in exp['network']:
        edge_switches = exp['network']['edge_switches']
    else:
        edge_switches = ['s{}'.format(i + 1) for i in range(n_switches)]

    # Create basic host dicts
    hosts = {}
    ip2host = {}
    for i in range(n_switches):
        snum = i + 1
        sname = 's{}'.format(snum)
        if sname in edge_switches:
            for j in range(hosts_per_switch):
                hnum = (snum - 1)*hosts_per_switch + j + 1
                hname = 'h{}'.format(hnum)
                hosts[hname] = {
                    'name': hname,
                    'num': hnum,
                    'ip': '10.0.{}.{}'.format(snum, hnum),
                    'mac': '08:00:00:00:{:02X}:{:02X}'.format(snum, hnum),
                }
                ip2host['10.0.{}.{}'.format(snum, hnum)] = hname
        
    # Load build wokrload log json file
    with open(bwl_json) as f:
        total_pkts = json.load(f)
    
    recvd_pkts = {}

    for host, hinfo in hosts.items():
        df = pd.read_csv('{}/{}_receiver.txt'.format(logs_dir, hinfo['name']))
        df['src'] = df['src'].apply(lambda x: ip2host[x])
        df['dst'] = hinfo['name']
        df['num'] = (2**32 * df['tos']) + df['id']
        df['len'] = 64 - df['ttl']
        df = df[['src', 'dst', 'num', 'len']]
        for src, pkts in df.groupby('src'):
            if src not in recvd_pkts:
                recvd_pkts[src] = {}
            recvd_pkts[src][hinfo['name']] = pkts
    for src in hosts.keys():
        if src not in recvd_pkts:
            recvd_pkts[src] = {}
        for dst in hosts.keys():
            if src == dst: continue
            if dst not in recvd_pkts[src]:
                recvd_pkts[src][dst] = pd.DataFrame(columns=('src', 'dst', 'num', 'len'))


    ana = pd.DataFrame(columns=('src', 'dst', 'expected', 'received', 'lost', 'reordered'))
    ana_lst = pd.DataFrame(columns=('min', 'mean', 'median', 'max'))
    ana_reo = pd.DataFrame(columns=('min', 'mean', 'median', 'max'))

    stats = {}
    stats['total'] = {
        'n_expected': 0,
        'n_normal': 0,
        'p_normal': None,
        'normal': list(),
        'n_reordered': 0,
        'p_reordered': None,
        'reordered': list(),
        'n_lost': 0,
        'p_lost': None,
        'lost': list()
    }


    for src in hosts.keys():
        stats[src] = {}
        for dst in hosts.keys():
            if src == dst: continue
            expected = total_pkts[src][dst]
            received = len(recvd_pkts[src][dst])
            lost = expected - received
            reordered = 0
            max_num = -1
            reo = []
            lst = []
            nrml = []
            for num in recvd_pkts[src][dst]['num']:
                if num < max_num:
                    reordered = reordered + 1
                    reo.append(num)
                else:
                    nrml.append(((num + 1)/expected)*100)
                max_num = max(max_num, num)
            if lost > 0:
                recs = set(recvd_pkts[src][dst]['num'])
                alll = set(range(expected))
                lst = pd.Series(list(alll - recs))
                lst = ((lst + 1) / expected) * 100
                lst_min = lst.min()
                lst_max = lst.max()
                lst_mean = lst.mean()
                lst_median = lst.median()
            if reordered > 0:
                reo = pd.Series(reo)
                reo = ((reo + 1) / expected) * 100
                reo_min = reo.min()
                reo_max = reo.max()
                reo_mean = reo.mean()
                reo_median = reo.median()
            idx = len(ana)
            ana.loc[idx] = [src, dst, expected, received, lost, reordered]
            if lost > 0:
                ana_lst.loc[idx] = [lst_min, lst_mean, lst_median, lst_max]
            if reordered > 0:
                ana_reo.loc[idx] = [reo_min, reo_mean, reo_median, reo_max]
            
            stats[src][dst] = {
                'n_expected': expected,
                'n_normal': received,
                'p_normal': received*100.0/expected,
                'normal': nrml,
                'n_reordered': reordered,
                'p_reordered': reordered*100.0/expected,
                'reordered': list(reo),
                'n_lost': lost,
                'p_lost': lost*100.0/expected,
                'lost': list(lst),
            }
            stats['total']['n_expected'] = stats['total']['n_expected'] + expected
            stats['total']['n_normal'] = stats['total']['n_normal'] + received
            stats['total']['normal'] = stats['total']['normal'] + nrml
            stats['total']['n_reordered'] = stats['total']['n_reordered'] + reordered
            stats['total']['reordered'] = stats['total']['reordered'] + list(reo)
            stats['total']['n_lost'] = stats['total']['n_lost'] + lost
            stats['total']['lost'] = stats['total']['lost'] + list(lst)

    stats['total']['p_normal'] = stats['total']['n_normal']*100.0/stats['total']['n_expected']
    stats['total']['p_reordered'] = stats['total']['n_reordered']*100.0/stats['total']['n_expected']
    stats['total']['p_lost'] = stats['total']['n_lost']*100.0/stats['total']['n_expected']

    with open(logs_dir + '/analyze_logs.json', 'w') as f:
        json.dump(stats, f)

    if quiet is not True:
        for idx, row in ana.iterrows():
            perc = (row['expected'] - row['received'])*100/row['expected']
            print(f"src={row['src']:<3} dst={row['dst']:<3} expected={row['expected']:6d} received={row['received']:6d} lost={row['lost']:6d} {perc:6.2f}% reordered={row['reordered']:6d}")
            if row['lost'] > 0:
                row_lst = ana_lst.loc[idx]
                print(f"    loss markers: min={row_lst['min']:6.2f}% mean={row_lst['mean']:6.2f}% median={row_lst['median']:6.2f}% max={row_lst['max']:6.2f}%")
            if row['reordered'] > 0:
                row_reo = ana_reo.loc[idx]
                print(f"    reorder markers: min={row_reo['min']:6.2f}% mean={row_reo['mean']:6.2f}% median={row_reo['median']:6.2f}% max={row_reo['max']:6.2f}%")
            
        perc = (ana['expected'].sum() - ana['received'].sum())*100/ana['expected'].sum()
        print(f"\nsrc=all dst=all expected={ana['expected'].sum():6d} received={ana['received'].sum():6d} lost={ana['lost'].sum():6d} {perc:6.2f}% reordered={ana['reordered'].sum():6d}")
        if ana['lost'].sum() > 0:
            print(f"    loss markers: min={ana_lst['min'].min():6.2f}% mean={ana_lst['mean'].mean():6.2f}% median={ana_lst['median'].median():6.2f}% max={ana_lst['max'].max():6.2f}%")
        if ana['reordered'].sum() > 0:
            print(f"    reorder markers: min={ana_reo['min'].min():6.2f}% mean={ana_reo['mean'].mean():6.2f}% median={ana_reo['median'].median():6.2f}% max={ana_reo['max'].max():6.2f}%")
    
    return ana['lost'].sum(), ana['reordered'].sum()

if __name__ == '__main__':
    args = docopt(__doc__)
    main(args['<exp_json>'], args['<bwl_json>'], args['<logs_dir>'])
