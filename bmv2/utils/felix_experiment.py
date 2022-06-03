from __future__ import print_function

import json
import os
import subprocess
import sys
import time


def run(mn, net_cli, exp_json='config/experiment.json'):
    # Load main experiment definition json file
    with open(exp_json) as f:
        exp = json.load(f)
    
    # Get Python3 path
    with open('/tmp/python3path') as f:
        python3path = f.read().strip()

    # Read base parameters into variables
    n_switches = exp['network']['n_switches']
    hosts_per_switch = exp['network']['hosts_per_switch']
    if 'edge_switches' in exp['network']:
        edge_switches = exp['network']['edge_switches']
    else:
        edge_switches = ['s{}'.format(i + 1) for i in range(n_switches)]
    run_workload = exp['run_workload'] if 'run_workload' in exp else False
    sim_failures = exp['sim_failures'] if 'sim_failures' in exp else False
    wl = exp['workload']
    p4prog = exp['p4prog']

    # Create basic host dicts
    hosts = {}
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

    # Start Routing
    routing_proc = None
    routing_stdout = None
    print('\nStarting Routing Script:', p4prog.capitalize())
    with open('/tmp/felix_routing_exit_flag', 'w') as f:
        f.write('0')
    if p4prog == 'felix':
        cmd = ['sudo', python3path, '-u', 'felix_routing.py', 'config/topology.json']
        routing_stdout = open('logs/felix_routing.txt', 'w')
        routing_proc = subprocess.Popen(cmd, stdout=routing_stdout, preexec_fn=os.setpgrp)
        print('Process received PID:', routing_proc.pid)
    elif p4prog == 'classic':
        cmd = ['sudo', python3path, '-u', 'classic_routing.py', 'config/topology.json']
        routing_stdout = open('logs/classic_routing.txt', 'w')
        routing_proc = subprocess.Popen(cmd, stdout=routing_stdout, preexec_fn=os.setpgrp)
        print('Process received PID:', routing_proc.pid)
    else:
        print('\nCould not start routing script, invalid name!')

    if run_workload is True:
        slowdown = exp['slowdown']
        duration = wl['duration']*slowdown
        TIMEOUT_SLACK = 10
        # Find hosts that will be sending and receiving traffic
        send_hosts = set()
        recv_hosts = set()
        for demand in wl['demands']:
            send_hosts.add(demand['src'])
            recv_hosts.add(demand['dst'])
        
        # Start traffic receiving script for each of those hosts
        print('\nStarting tcpreplay receivers')
        BASE_PORT = 50000
        recv_pids = {}
        for recv_host in recv_hosts:
            # Get info
            dst_ip = hosts[recv_host]['ip']
            dst_port = BASE_PORT
            log_file = '{}_receiver.txt'.format(recv_host)
            # Send command
            cmd = 'timeout -sSIGINT {timeout} '
            cmd += 'sudo {python3path} -u'
            cmd += ' traffic_receiver.py {dst_name} {dst_ip} {dst_port} '
            cmd += '&> logs/{log_file} &'
            cmd = cmd.format(
                python3path=python3path,
                timeout=duration + 2*TIMEOUT_SLACK,
                dst_name=recv_host,
                dst_ip=dst_ip,
                dst_port=dst_port,
                log_file=log_file
            )
            print('{}$ {}'.format(recv_host, cmd))
            mn.getNodeByName(recv_host).cmd(cmd)
            # Save process info
            recv_pids[recv_host] = int(mn.getNodeByName(recv_host).cmd('echo $!'))

        time.sleep(TIMEOUT_SLACK)

        # Start tcpreplay
        print('\nStarting tcpreplay senders')
        send_pids = {}
        for send_host in send_hosts:
            # Get info
            pcap_file = '{}/{}.pcap'.format(wl['base_dir'], send_host)
            log_file = '{}_sender.txt'.format(send_host)
            # Send command
            cmd = 'timeout -sSIGINT {timeout} '
            cmd += 'tcpreplay --intf1=eth0 --preload-pcap --stats=1 {pcap_file} '
            cmd += '&> logs/{log_file} &'
            cmd = cmd.format(
                timeout=duration + TIMEOUT_SLACK,
                pcap_file=pcap_file,
                log_file=log_file
            )
            print('{}$ {}'.format(send_host, cmd))
            mn.getNodeByName(send_host).cmd(cmd)
            # Save process info
            send_pids[send_host] = int(mn.getNodeByName(send_host).cmd('echo $!'))

        # Only run ralph if "sim_failures" is True
        if sim_failures is True:
            # Start Ralph
            print('\nStarting Ralph')
            cmd = ['sudo', python3path, '-u', 'ralph.py', 'config/topology.json']
            r_stdout = open('logs/ralph.txt', 'w')
            ralph = subprocess.Popen(cmd, stdout=r_stdout)
            print('Process received PID:', ralph.pid)

            # Wait for Ralph to finish
            print('Waiting for Ralph to finish')
            ralph.wait()
            r_stdout.close()

        # Wait for tcpreplay senders to finish
        print('\nWaiting for tcpreplay senders to finish')
        for send_host in send_hosts:
            print('Sender at {src}'.format(src=send_host), end='')
            finished = 0
            while finished == 0:
                mn.getNodeByName(send_host).cmd('ps -p {}'.format(send_pids[send_host]))
                finished = int(mn.getNodeByName(send_host).cmd('echo $?'))
                if finished == 0:
                    print('.', end='')
                    sys.stdout.flush()
                    time.sleep(1)
            print()
        
        # Wait for tcpreplay receivers to finish
        print('\nWaiting for tcpreplay receivers to finish')
        for recv_host in recv_hosts:
            print('Receiver at {dst}'.format(dst=recv_host), end='')
            finished = 0
            while finished == 0:
                mn.getNodeByName(recv_host).cmd('ps -p {}'.format(recv_pids[recv_host]))
                finished = int(mn.getNodeByName(recv_host).cmd('echo $?'))
                if finished == 0:
                    print('.', end='')
                    sys.stdout.flush()
                    time.sleep(1)
            print()
        
        # net_cli()
    else:
        net_cli()

    # Stop Routing Script
    print('\nSignalling Routing Script to Finish')
    with open('/tmp/felix_routing_exit_flag', 'w') as f:
        f.write('1')
    print('Waiting for Routing Script to Finish')
    sys.stdout.flush()
    time.sleep(10)
    routing_proc.kill()
    routing_stdout.close()
