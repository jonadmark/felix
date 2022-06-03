import os
import signal
import socket
import subprocess
import sys
import time

from scapy.layers.inet import IP, ICMP, UDP
from scapy.all import Raw
from scapy.sendrecv import AsyncSniffer


output = 'src,tos,id,ttl,ns\n'
def add_to_output(line):
    global output
    output = output + line

def print_output():
    global output
    print(output)
    output = ''


def main(dst_name, dst_ip, dst_port):
    # print('# {} {} {}'.format(dst_name, dst_ip, dst_port))
    sock = socket.socket(socket.AF_INET,  # Internet
                         socket.SOCK_DGRAM)  # UDP
    sock.bind((dst_ip, dst_port))

    t = AsyncSniffer(
        iface='eth0',
        # lfilter =lambda x: x.haslayer(UDP) and x[IP].dst == dst_ip,
        filter='ip dst host {}'.format(dst_ip),
        # stop_filter=lambda x: x.haslayer(ICMP),
        prn=lambda x: add_to_output('{},{},{},{},{}\n'.format(x[IP].src, x[IP].tos,
                                                          x[IP].id, x[IP].ttl, int.from_bytes(x[Raw].load[:4], 'big'))),
        store=False,
    )
    t.start()

    try:
        while True:
            sock.recvfrom(1514)
    except KeyboardInterrupt:
        print_output()
        t.stop()
        t.join()

    return


if __name__ == '__main__':
    if len(sys.argv) != 4:
        print('Usage: tcpreplay_receiver.py <dst_name> <dst_IP> <dst_port>')
        exit(1)
    main(sys.argv[1], sys.argv[2], int(sys.argv[3]))