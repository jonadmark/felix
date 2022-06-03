import os
import subprocess
import time


class FelixSwitch:
    def __init__(self, sw_info, script='felix'):
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
                self.add_opposite_entry(peer, [port])
        self.loc_state = None
        # Normal Forwarding
        self.nf_members = {}
        self.nf_groups = {}
        # Alternative Forwarding
        self.af_members = {}
        self.af_groups = {}
        self.af_entries = {}
        self.af_entry_handles = {}
        self.next_af_handle = 0
    
    def __del__(self):
        self.close = True
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
        reg_wr = 'register_write ingress.net_state 0 0'
        self._cmd(reg_wr)
        reg_wr = 'register_write ingress.prev_net_state 0 0'
        self._cmd(reg_wr)
        reg_wr = 'register_write ingress.suspect 0 0'
        self._cmd(reg_wr)
        reg_wr = 'register_write ingress.latent_net_state 0 0'
        self._cmd(reg_wr)
        
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
    
    def add_opposite_entry(self, opposite, ports):
        add_entry = 'table_add ingress.opposite_table ingress.set_opposite {} => {}'
        loc_state_change = 0
        for port in ports:
            loc_state_change = loc_state_change | (1 << (port - 1))
        opposite_num = int(opposite[1:])
        self._cmd(add_entry.format(loc_state_change, opposite_num))

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

    def add_nrml_fwding_entry_host(self, host):
        # Create member pointing to port connected to host
        create_member = 'act_prof_create_member ingress.nrml_selector nrml_fwd {} 0'
        port = self.adj[host['name']]
        member_id = '{}:{}'.format(host['name'], port)
        create_member = create_member.format(port)
        self._cmd(create_member)
        member_handle = len(self.nf_members)
        self.nf_members[member_id] = {'handle': member_handle,
                                        'dst_switch': None,
                                        'port': port}
        # Add forwarding entry
        add_entry = 'table_indirect_add ingress.nrml_fwding_table {} => {}'
        add_entry = add_entry.format(host['ip'][:-3] + '/32', member_handle)
        self._cmd(add_entry)
    
    def add_nrml_fwding_entry(self, dstinfo, next_hops):
        # Create act_prof_members pointing to each possible next hop
        member_handles = []
        for next_hop in next_hops:
            port = self.adj[next_hop]
            member_id = '{}:{}'.format(dstinfo['name'], port)
            if member_id not in self.nf_members:
                # Create member pointing to port connected to switch
                create_member = 'act_prof_create_member ingress.nrml_selector nrml_fwd {} {}'
                create_member = create_member.format(port, dstinfo['num'])
                self._cmd(create_member)
                member_handle = len(self.nf_members)
                self.nf_members[member_id] = {
                    'handle': member_handle, 'dst_switch': dstinfo['name'],
                    'port': port
                }
                member_handles.append(member_handle)
            else:
                member_handles.append(self.nf_members[member_id]['handle'])
        member_handles.sort()
        # Create group containing all possible next hops
        hs_string = ','.join([str(mh) for mh in member_handles])
        group_id = '{}:{}'.format(dstinfo['name'], hs_string)
        group_handle = None
        if group_id not in self.nf_groups:
            # Create group
            create_group = 'act_prof_create_group ingress.nrml_selector'
            self._cmd(create_group)
            group_handle = len(self.nf_groups)
            self.nf_groups[group_id] = {
                'handle': group_handle, 'members': []
            }
            # Add members to group
            for next_hop, member_handle in zip(next_hops, member_handles):
                add_m2g = 'act_prof_add_member_to_group ingress.nrml_selector {} {}'
                add_m2g = add_m2g.format(member_handle, group_handle)
                self._cmd(add_m2g)
                self.nf_groups[group_id]['members'].append(next_hop)
        else:
            group_handle = self.nf_groups[group_id]['handle']
        # Add forwarding entry
        add_entry = 'table_indirect_add_with_group ingress.nrml_fwding_table {} => {}'
        add_entry = add_entry.format(dstinfo['ip'], group_handle)
        self._cmd(add_entry)
    
    def add_alt_fwding_entry(self, net_state, dstinfo, next_hops):
        # Create members pointing to each possible next hop
        member_handles = []
        for next_hop in next_hops:
            port = self.adj[next_hop]
            member_id = '{}'.format(port)
            if member_id not in self.af_members:
                # Create member pointing to port connected to s0
                create_member = 'act_prof_create_member ingress.alt_selector alt_fwd {}'
                create_member = create_member.format(port)
                self._cmd(create_member)
                member_handle = len(self.af_members)
                self.af_members[member_id] = {'handle': member_handle,
                                                'port': port}
                member_handles.append(member_handle)
            else:
                member_handles.append(self.af_members[member_id]['handle'])
        member_handles.sort()
        # Create group containing all possible next hops
        hs_string = ','.join([str(mh) for mh in member_handles])
        group_id = '{}'.format(hs_string)
        group_handle = None
        if group_id not in self.af_groups:
            # Create group
            create_group = 'act_prof_create_group ingress.alt_selector'
            self._cmd(create_group)
            group_handle = len(self.af_groups)
            self.af_groups[group_id] = {'handle': group_handle, 'members': []}
            # Add members to group
            for next_hop, member_handle in zip(next_hops, member_handles):
                add_m2g = 'act_prof_add_member_to_group ingress.alt_selector {} {}'
                add_m2g = add_m2g.format(member_handle, group_handle)
                self._cmd(add_m2g)
                self.af_groups[group_id]['members'].append(next_hop)
        else:
            group_handle = self.af_groups[group_id]['handle']
        # Add forwarding entry
        entry_handle = self.get_new_alt_entry_handle()
        if net_state not in self.af_entries:
            self.af_entries[net_state] = {}
        self.af_entries[net_state][dstinfo['name']] = {'handle': entry_handle}
        add_entry = 'table_indirect_add_with_group ingress.alt_fwding_table {} {} => {}'
        add_entry = add_entry.format(net_state, dstinfo['num'], group_handle)
        self._cmd(add_entry)
    
    def get_new_alt_entry_handle(self):
        found = False
        handle = 0
        while found is False:
            if self.next_af_handle not in self.af_entry_handles:
                found = True
                handle = self.next_af_handle
                self.af_entry_handles[handle] = {'open': False, 'dels': 0}
            elif self.af_entry_handles[self.next_af_handle]['open']:
                found = True
                handle = self.next_af_handle
                self.af_entry_handles[handle]['open'] = False
            self.next_af_handle = self.next_af_handle + 1
        return handle

    def del_alt_fwding_entry(self, handle):
        act_handle = 0x1000000*self.af_entry_handles[handle]['dels'] + handle
        remove_entry = 'table_indirect_delete ingress.alt_fwding_table {}'
        remove_entry = remove_entry.format(act_handle)
        self._cmd(remove_entry)
        self.af_entry_handles[handle]['dels'] += 1
        self.af_entry_handles[handle]['open'] = True
        if handle < self.next_af_handle:
            self.next_af_handle = handle
    
    def trim_alt_fwding_table(self, states_to_keep):
        net_states_to_delete_entries = []
        for net_state, destinations in self.af_entries.items():
            if net_state in states_to_keep: continue
            for dst, entryinfo in destinations.items():
                self.del_alt_fwding_entry(entryinfo['handle'])
            net_states_to_delete_entries.append(net_state)
        for net_state in net_states_to_delete_entries:
            del self.af_entries[net_state]
    
    def clear_alt_fwding_table(self):
        # Clear table
        clear_table = 'table_clear ingress.alt_fwding_table'
        self._cmd(clear_table)
        # Reset structures
        self.af_members = {}
        self.af_groups = {}
        self.af_entries = {}
        self.af_entry_handles = {}
        self.next_af_handle = 0

    def add_state_transition(self, cur_net_state, peerinfo, new_net_state, latent_net_state):
        add_entry = 'table_add ingress.state_transition_table ingress.set_new_net_state {} {} => {} {}'
        # loc_state = self.d_loc_state
        # for u, v in failed_links:
        #     if u == self.name:
        #         loc_state = loc_state & ~(1<<(self.adj[v] - 1))
        #     elif v == self.name:
        #         loc_state = loc_state & ~(1<<(self.adj[u] - 1))
        add_entry = add_entry.format(cur_net_state, peerinfo['num'],
                                     new_net_state, latent_net_state)
        self._cmd(add_entry)
    
    def clear_state_transition_table(self):
        clear_table = 'table_clear ingress.state_transition_table'
        self._cmd(clear_table)


