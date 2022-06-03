# Wreck-it Ralph
import json
import sys
import time

import felix_switch, classic_switch


def main(p4prog, topology_json):
    
    with open(topology_json) as f:
        net = json.load(f)
    
    switches = {}
    for sname, sinfo in net['switches'].items():
        if sname == 's0': continue
        if p4prog == 'felix':
            switches[sname] = felix_switch.FelixSwitch(sinfo, script='ralph')
        elif p4prog == 'classic':
            switches[sname] = classic_switch.ClassicSwitch(sinfo, script='ralph')
        switches[sname].set_all_interfaces_up()

    while True:
        try:
            cmd = input('>>> ')
        except EOFError:
            print('EOF')
            return
        scmd = cmd.split(' ')

        if cmd == 'exit' or cmd == 'EOF':
            break
        elif cmd == 'reset':
            for sname, sw in switches.items():
                sw.reset_all_interfaces_up()
        elif scmd[0] == 'fail' or scmd[0] == 'fail_link' or scmd[0] == 'fl':
            uname = scmd[1]
            vname = scmd[2]

            switches[uname].set_interface_down(vname)
            switches[vname].set_interface_down(uname)
        elif scmd[0] == 'fail_node' or scmd[0] == 'fn':
            uname = scmd[1]
            delay = float(scmd[2]) if len(scmd) == 3 else None

            switches[uname].set_switch_down()
            for vname in switches[uname].adj.keys():
                if vname != 's0' and vname[0] != 'h':
                    switches[vname].set_interface_down(uname)


if __name__ == '__main__':
    if len(sys.argv) == 3:
        main(sys.argv[1], sys.argv[2])
    else:
        print('Usage: python3 interactive_ralph.py felix|classic <topology_json>')
        print('Using default experiment... felix')
        print('Using default file... config/topology.json')
        main('felix', 'config/topology.json')
