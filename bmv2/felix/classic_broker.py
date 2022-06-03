import collections
import queue
import sys
import threading
import time

from scapy.all import sniff, Packet, IntField, Ether, bind_layers


CPU_PORT = 99


ClassicAnnTuple = collections.namedtuple(
    'ClassicAnnTuple', ['announcer', 'new_loc_state', 'prev_loc_state'])


class ClassicAnnouncement(Packet):
    name = 'ClassicAnnouncement'
    fields_desc = [
        IntField('announcer', 0),
        IntField('new_loc_state', 0),
        IntField('prev_loc_state', 0),
    ]

    def to_tuple(self):
        announcer = 's{}'.format(self.announcer)
        return ClassicAnnTuple(announcer, self.new_loc_state, self.prev_loc_state)


#
bind_layers(Ether, ClassicAnnouncement, type=0x88B5)


class PacketSniffer(threading.Thread):
    def __init__(self, switch_name, interface, ann_queue, verbose=False):
        threading.Thread.__init__(self)
        self.switch_name = switch_name
        self.interface = interface
        self.ann_queue = ann_queue
        self.VERBOSE = verbose

    def process_packet(self, pkt):
        if ClassicAnnouncement in pkt:
            self.ann_queue.put(pkt[ClassicAnnouncement].to_tuple())

    def run(self):
        if self.VERBOSE:
            print('Sniffing interface {}'.format(self.interface))
        sniff(iface=self.interface, prn=lambda x: self.process_packet(x))

def announcements(switches, verbose=False):
    ann_queue = queue.Queue()

    if verbose:
        print('Creating sniffer threads.')
    sniffers = []
    for sname, sinfo in switches.items():
        if sname == 's0':
            continue
        interface = 's0-eth{}'.format(sinfo['num'])
        sniffers.append(PacketSniffer(sname, interface, ann_queue))

    if verbose:
        print('Starting the sniffer threads.')
    for s in sniffers:
        s.start()

    return ann_queue


class DelayedEntryUpdates(threading.Thread):
    def __init__(self, switch_manager, prop_delay, install_delay, entries):
        threading.Thread.__init__(self)
        self.switch_manager = switch_manager
        self.prop_delay = prop_delay
        self.install_delay = install_delay
        self.entries = entries

    def run(self):
        time.sleep(self.prop_delay)
        with open('/tmp/felix_routing_exit_flag') as f:
            if f.read() == '1':
                return
        for entry in self.entries:
            time.sleep(self.install_delay)
            with open('/tmp/felix_routing_exit_flag') as f:
                if f.read() == '0':
                    self.switch_manager.set_nrml_fwding_entry(entry[0], entry[1])

def send_entry_updates(switch_manager, prop_delay, install_delay, entries):
    thr = DelayedEntryUpdates(switch_manager, prop_delay, install_delay, entries)
    thr.start()
