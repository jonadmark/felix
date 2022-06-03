import os
import subprocess
import time


class ClassicSwitch:
    def __init__(self, sw_info, script='classic'):
        #
        self.thrift_port = sw_info['thrift_port']
        cmd = ['runtime_CLI.py', '--thrift-port', str(self.thrift_port)]
        self.log = open('logs/{}_{}.log'.format(sw_info['name'], script), 'w')
        self.conn = subprocess.Popen(cmd, stdin=subprocess.PIPE,
                                     stdout=self.log, stderr=subprocess.STDOUT,
                                     text=True)
        #
        self.id = sw_info['id']
        self.name = sw_info['name']
        self.num = sw_info['num']
        self.ip = sw_info['ip']
        self.mac = sw_info['mac']
        self.adj = sw_info['adj']
        #
        self.d_loc_state = 0
        for peer, port in self.adj.items():
            if peer != 's0' and peer[0] != 'h':
                self.d_loc_state = self.d_loc_state | (1 << (port - 1))
        self.loc_state = None
        # Normal Forwarding
        self.nf_member_handles = {}
        self.nf_groups = {}

    def __del__(self):
        self._cmd('EOF')
        self.conn.wait()
        self.log.close()

    def _cmd(self, cmdline, flush=True):
        clean_cmdline = cmdline.strip('\n')
        self.log.write('{}\n'.format(clean_cmdline))
        self.conn.stdin.write(clean_cmdline + '\n')
        if flush:
            self.conn.stdin.flush()

    def init_state(self, reset=False):
        reg_wr1 = ''
        if reset:
            reg_wr1 = 'register_write ingress.prev_loc_state 0 0\n'
        else:
            reg_wr1 = 'register_write ingress.prev_loc_state 0 {}\n'
            reg_wr1 = reg_wr1.format(self.d_loc_state)
        reg_wr2 = 'register_write ingress.loc_state 0 {}\n'
        reg_wr2 = reg_wr2.format(self.d_loc_state)
        self._cmd(reg_wr1 + reg_wr2)
        self.loc_state = self.d_loc_state

    def set_interface_down(self, peer):
        if peer == 's0' or peer[0] == 'h':
            raise Exception('Invalid interface (to s0 or host) to take down.')
        reg_wr = 'register_write ingress.loc_state 0 {}'
        self.loc_state = self.loc_state & ~(1<<(self.adj[peer] - 1))
        self._cmd(reg_wr.format(self.loc_state))
    
    def set_link_down(self, peer):
        if peer == 's0' or peer[0] == 'h':
            raise Exception('Invalid link (connected to s0 or host) to take down.')
        if_down = 'ifconfig {}-eth{} down'
        if_down = if_down.format(self.name, self.adj[peer])
        self.log.write('{}\n'.format(if_down))
        os.system(if_down)

    def set_all_interfaces_up(self, reset=False):
        if_up = 'ifconfig {}-eth{} up'
        for port in self.adj.values():
            self.log.write('{}\n'.format(if_up.format(self.name, port)))
            os.system(if_up.format(self.name, port))
        #
        self.init_state(reset=reset)

    def reset_all_interfaces_up(self):
        self.set_all_interfaces_up(reset=True)

    def reset_switch_up(self):
        self.set_all_interfaces_up(reset=True)

    def set_switch_down(self):
        cmd = ''
        if_down = 'ifconfig {}-eth{} down'
        for port in self.adj.values():
            cmd = cmd + '{}\n'.format(if_down.format(self.name, port))
        self.log.write(cmd)
        os.system(cmd)
    
    def _create_forwarding_act_prof_members(self):
        # Create normal forwarding members
        apcm = 'act_prof_create_member ingress.nrml_selector nrml_fwd {}'
        for peer, port in self.adj.items():
            new_handle = len(self.nf_member_handles)
            self.nf_member_handles[peer] = new_handle
            self._cmd(apcm.format(port))
        # # Create drop member
        # apcm = 'act_prof_create_member ingress.nrml_selector drop'
        # new_handle = len(self.nf_member_handles)
        # self.nf_member_handles['drop'] = new_handle
        # self._cmd(apcm)


    def add_nrml_fwding_entry_host(self, host):
        # Make sure base members exist
        if len(self.nf_member_handles) == 0:
            self._create_forwarding_act_prof_members()
        # Add forwarding entry
        add_entry = 'table_indirect_add ingress.nrml_fwding_table {} => {}'
        add_entry = add_entry.format(host['ip'][:-3] + '/32',
                                     self.nf_member_handles[host['name']])
        self._cmd(add_entry)

    def set_nrml_fwding_entry(self, dstinfo, next_hops):
        # Make sure base members exist
        if len(self.nf_member_handles) == 0:
            self._create_forwarding_act_prof_members()
        # Make sure group and forwarding entry exists
        dstname = dstinfo['name']
        new_group = False
        if dstname not in self.nf_groups:
            # Create group
            create_group = 'act_prof_create_group ingress.nrml_selector'
            self._cmd(create_group)
            new_handle = len(self.nf_groups)
            self.nf_groups[dstname] = {
                "handle": new_handle,
                "members": []
            }
            new_group = True
        # Figure out members to add and to remove
        to_add = set(next_hops) - set(self.nf_groups[dstname]['members'])
        # to_add = sorted(next_hops)
        to_del = set(self.nf_groups[dstname]['members']) - set(next_hops)
        # to_del = self.nf_groups[dstname]['members']
        self.nf_groups[dstname]['members'] = next_hops
        group_handle = self.nf_groups[dstname]['handle']
        # Add new members to group
        for adj in to_add:
            member_handle = self.nf_member_handles[adj]
            add_m2g = 'act_prof_add_member_to_group ingress.nrml_selector {} {}'
            add_m2g = add_m2g.format(member_handle, group_handle)
            self._cmd(add_m2g)
        # And remove deprecated members from group
        for adj in to_del:
            member_handle = self.nf_member_handles[adj]
            add_m2g = 'act_prof_remove_member_from_group ingress.nrml_selector {} {}'
            add_m2g = add_m2g.format(member_handle, group_handle)
            self._cmd(add_m2g)
        # Create forwarding entry (if new group)
        if new_group is True:
            add_entry = 'table_indirect_add_with_group ingress.nrml_fwding_table {} => {}'
            add_entry = add_entry.format(dstinfo['ip'], new_handle)
            self._cmd(add_entry)
