import json
import math


def main(base_directory, datasets):
    
    for ds in datasets:
        ds_directory = '{}/{}'.format(base_directory, ds['directory'])
        if ds["name"] in ["FatTree"]:
            continue
        for net in ds['networks']:
            print(ds['name'], net)
            
            # GRAPH
            graph_filename = '{}/{}.graph'.format(ds_directory, net)
            json_filename = '{}/{}.graph.json'.format(ds_directory, net)
            text_filename = '{}/{}.graph.txt'.format(ds_directory, net)
            
            net_json = {}
            with open(graph_filename) as gf:
                for line in gf:
                    if line == '\n':
                        continue
                    else:
                        sl = line.split(' ')
                        if sl[0] == 'NODES':
                            net_json['n_nodes'] = int(sl[1])
                            net_json['nodes'] = []
                            
                            gf.readline()
                            node_ID = 0
                            for i in range(net_json['n_nodes']):
                                line = gf.readline()
                                sl = line.split(' ')
                                node = {
                                    'id': node_ID,
                                    'label': sl[0],
                                    'x': float(sl[1]),
                                    'y': float(sl[2])
                                }
                                net_json['nodes'].append(node)
                                node_ID = node_ID + 1
                            
                        elif sl[0] == 'EDGES':
                            net_json['n_edges'] = int(sl[1])
                            net_json['edges'] = []
                            
                            gf.readline()
                            edge_ID = 0
                            for i in range(net_json['n_edges']):
                                line = gf.readline()
                                sl = line.split(' ')
                                if ds["name"] in ["DEFO"]:
                                    delay = int(sl[5])*1000
                                else:
                                    delay = int(sl[5])
                                edge = {
                                    'id': edge_ID,
                                    'label': sl[0],
                                    'src': int(sl[1]),
                                    'dst': int(sl[2]),
                                    'weight': int(sl[3]),
                                    'bw': int(sl[4]),
                                    'delay': delay
                                }
                                net_json['edges'].append(edge)
                                edge_ID = edge_ID + 1

            with open(json_filename, 'w') as jf:
                json.dump(net_json, jf, indent=2)
            
            with open(text_filename, 'w') as tf:
                tf.write('{} {}\n'.format(net_json['n_nodes'], net_json['n_edges']))
                for e in net_json['edges']:
                    tf.write('{} {}\n'.format(e['src'], e['dst']))

            # DEMANDS
            for demand in ds['demands']:
                matrix_json = {}
                
                demands_filename = '{}/{}{}.demands'.format(ds_directory, net, demand)
                json_filename = '{}/{}{}.demands.json'.format(ds_directory, net, demand)
                
                demands_json= {}
                with open(demands_filename) as df:
                    for line in df:
                        if line == '\n':
                            continue
                        else:
                            sl = line.split(' ')
                            if sl[0] == 'DEMANDS':
                                demands_json['n_demands'] = int(sl[1])
                                demands_json['demands_list'] = []
                                demands_json['demands_matrix'] = []
                                for i in range(net_json['n_nodes']):
                                    demands_json['demands_matrix'].append([0]*net_json['n_nodes'])
                                
                                df.readline()
                                demand_ID = 0
                                for i in range(demands_json['n_demands']):
                                    line = df.readline()
                                    sl = line.split(' ')
                                    
                                    src = int(sl[1])
                                    dst = int(sl[2])
                                    bw = int(sl[3])
#                                     bw = int(int(sl[3])*0.55)
                                    pktrate = int(math.ceil(bw*1000/(8*891)))  # avg 891-byte packets
                                    demand = {
                                        'id': demand_ID,
                                        'label': sl[0],
                                        'src': src,
                                        'dst': dst,
                                        'bw': bw,
                                        'pktrate': pktrate
                                    }
                                    demands_json['demands_matrix'][src][dst] = pktrate
                                    demands_json['demands_list'].append(demand)
                                    demand_ID = demand_ID + 1
                
                with open(json_filename, 'w') as jf:
                    json.dump(demands_json, jf, indent=2)

if __name__ == '__main__':

    input_filename = 'metadata.json'

    with open(input_filename) as f:
        args = json.load(f)

    base_directory = "./data/"

    main(base_directory, args['datasets'])
