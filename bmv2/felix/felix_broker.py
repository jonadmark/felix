import collections
import queue
import sys
import threading
import time

from scapy.all import sniff, Packet, IntField, BitField, Ether, bind_layers


CPU_PORT = 99


FelixAnnTuple = collections.namedtuple('FelixAnnTuple', ['new_net_state', 'announcer', 'opposite', 'prev_net_state', 'latent_net_state', 'n_transitions'])


class FelixAnnouncement(Packet):
    name = 'FelixAnnouncement'
    fields_desc = [
        IntField('new_net_state', 0),
        IntField('announcer', 0),
        IntField('opposite', 0),
        IntField('prev_net_state', 0),
        IntField('latent_net_state', 0),
        IntField('n_transitions', 0),
        # BitField('unused', 0, 240)
    ]

    def to_tuple(self):
        announcer = 's{}'.format(self.announcer)
        opposite = 's{}'.format(self.opposite)
        return FelixAnnTuple(self.new_net_state, announcer, opposite,
                             self.prev_net_state, self.latent_net_state,
                             self.n_transitions)
#
bind_layers(Ether, FelixAnnouncement, type=0x88B5)


class PacketSniffer(threading.Thread):
    def __init__(self, switch_name, interface, ann_queue, verbose=False):
        threading.Thread.__init__(self)
        self.switch_name = switch_name
        self.interface = interface
        self.ann_queue = ann_queue
        self.VERBOSE = verbose
    
    def process_packet(self, pkt):
        if FelixAnnouncement in pkt:
            self.ann_queue.put(pkt[FelixAnnouncement].to_tuple())
    
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
        for entry in self.entries['fwd']:
            time.sleep(self.install_delay)
            with open('/tmp/felix_routing_exit_flag') as f:
                if f.read() == '0':
                    self.switch_manager.add_alt_fwding_entry(entry[0], entry[1],
                                                             entry[2])
        for entry in self.entries['stt']:
            time.sleep(self.install_delay)
            with open('/tmp/felix_routing_exit_flag') as f:
                if f.read() == '0':
                    self.switch_manager.add_state_transition(entry[0], entry[1],
                                                             entry[2], entry[3])

def send_entry_updates(switch_manager, prop_delay, install_delay, entries):
    thr = DelayedEntryUpdates(switch_manager, prop_delay, install_delay, entries)
    thr.start()
