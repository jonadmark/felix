import json
import os
import random
import string
import sys

from multiprocessing import Pool

from scapy.all import Packet, Ether, IP, UDP, wrpcap


def gen_host_traffic(info):
    n_packets = {}
    all_traffic = []
    print('Generating packets for traffic from {}'.format(info['src']['name']))
    for demand in info['demands']:
        # Gen packets
        demand_traffic = gen_traffic(
            src=info['src'],
            dst=demand['dst'],
            rate=demand['rate'],
            duration=info['duration'],
            lorem=info['lorem']
        )
        # Store packets
        all_traffic = all_traffic + demand_traffic
        # Logging
        dst_name = demand['dst']['name']
        n_packets[dst_name] = len(demand_traffic)

    # Write packets to file
    all_traffic.sort(key=lambda x: x.time)
    src_name = info['src']['name']
    print('Writing packets from {} to pcap file'.format(src_name), flush=True)
    wrpcap(info['output_filename'], all_traffic)
    return n_packets


def gen_traffic(src, dst, rate, duration, lorem):
    BASE_PORT = 50000
    random.seed(42)
    maxframesize = 1518 - 4  # Frame Check Sequence
    hdslen = 14 + 20 + 8  # Eth + IPv4 + UDP
    msglen = maxframesize - hdslen

    t = 0.0 + (dst['num']/1000)
    ip_tos = 0
    ip_id = 0
    second = int(t)

    traffic = []
    while (t < float(duration)):
        # Build Packet
        beg = random.randint(0, 1e6 - msglen - 1)
        pkt = Ether()
        pkt = pkt / IP(src=src['ip'], dst=dst['ip'], tos=ip_tos, id=ip_id)
        pkt = pkt / UDP(sport=BASE_PORT + dst['num'],
                        dport=BASE_PORT)
        pkt = pkt / lorem[beg:beg+msglen]
        pkt.time = t
        traffic.append(pkt)
        # Calculate the arrival time for the next packet
        delay = 1.0/((rate*1e6)/(8*(hdslen + msglen)))
        noise = random.gauss(1, 0.1)
        t = t + noise*delay
        # Update identification fields (i.e., id and tos)
        ip_tos = ip_tos + ((ip_id + 1)//65536)
        ip_id = (ip_id + 1)%65536
    return traffic


def main(exp_json):
    global lorem

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
    slowdown = exp['slowdown']
    wl = exp['workload']
    duration = wl['duration']*slowdown
    multiplier = wl['multiplier'] if 'multiplier' in wl else 1.0

    # Create basic host dicts
    hosts = {}
    for i in range(n_switches):
        snum = i + 1
        sname = 's{}'.format(snum)
        # print(sname)
        if sname in edge_switches:
            for j in range(hosts_per_switch):
                hnum = (snum - 1)*hosts_per_switch + j + 1
                hname = 'h{}'.format(hnum)
                # print(hname)
                hosts[hname] = {
                    'name': hname,
                    'num': hnum,
                    'ip': '10.0.{}.{}'.format(snum, hnum),
                    'mac': '08:00:00:00:{:02X}:{:02X}'.format(snum, hnum),
                }
    

    # Create demand traffic pcap files
    letters = string.ascii_letters + string.digits
    lorem = ''.join(random.choice(letters) for i in range(int(1e6)))

    output_dir = '../../' + wl['base_dir']
    os.makedirs(output_dir, exist_ok=True)

    gen_info = {}
    for demand in wl['demands']:
        src_name = demand['src']
        # Create base info
        if src_name not in gen_info:
            gen_info[src_name] = {
                'src': hosts[src_name],
                'output_filename': '{}/{}.pcap'.format(output_dir, src_name),
                'duration': duration,
                'lorem': lorem,
                'demands': []
            }
        # Add new flow
        gen_info[src_name]['demands'].append({
            'dst': hosts[demand['dst']],
            'rate': (demand['rate']/slowdown)*multiplier  # Mbps
        })
    
    with Pool(16) as pool:
        result = pool.map(gen_host_traffic, gen_info.values())

    print(result)

    total_packets = {}
    for src_name, res in zip(gen_info.keys(), result):
        total_packets[src_name] = res
     
    with open('{}/build_workload_log.json'.format(output_dir), 'w') as f:
        json.dump(total_packets, f, indent=4)


if __name__ == '__main__':
    if len(sys.argv) == 2:
        main(sys.argv[1])
    elif len(sys.argv) == 3 and sys.argv[2] == 'dryrun':
        main(sys.argv[1])
    else:
        print('Usage: python3 build_workload.py <experiment_json> [dryrun]')
        sys.exit(1)