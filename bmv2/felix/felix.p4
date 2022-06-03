/* -*- P4_16 -*- */
#include <core.p4>
#include <v1model.p4>

const bit<32> BMV2_V1MODEL_INSTANCE_TYPE_NORMAL        = 0;
const bit<32> BMV2_V1MODEL_INSTANCE_TYPE_INGRESS_CLONE = 1;
const bit<32> BMV2_V1MODEL_INSTANCE_TYPE_EGRESS_CLONE  = 2;
const bit<32> BMV2_V1MODEL_INSTANCE_TYPE_COALESCED     = 3;
const bit<32> BMV2_V1MODEL_INSTANCE_TYPE_RECIRC        = 4;
const bit<32> BMV2_V1MODEL_INSTANCE_TYPE_REPLICATION   = 5;
const bit<32> BMV2_V1MODEL_INSTANCE_TYPE_RESUBMIT      = 6;

#define IS_NORMAL(std_meta) (std_meta.instance_type == BMV2_V1MODEL_INSTANCE_TYPE_NORMAL)
#define IS_RECIRCULATED(std_meta) (std_meta.instance_type == BMV2_V1MODEL_INSTANCE_TYPE_RECIRC)
#define IS_I2E_CLONE(std_meta) (std_meta.instance_type == BMV2_V1MODEL_INSTANCE_TYPE_INGRESS_CLONE)
#define IS_E2E_CLONE(std_meta) (std_meta.instance_type == BMV2_V1MODEL_INSTANCE_TYPE_EGRESS_CLONE)
#define IS_REPLICATED(std_meta) (std_meta.instance_type == BMV2_V1MODEL_INSTANCE_TYPE_REPLICATION)

const bit<16> BROADCAST_MC_GRP = 99;
const bit<16> SELECT_MC_GRP = 100;
const bit<32> CPU_PORT = 99;
// const bit<48> DELTA_TH = 100000;  // microseconds
const bit<48> DELTA_TH = 40000000;  // microseconds

////////////////////////////////////////////////////////////////
////////               HEADER DEFINITIONS               ////////
////////////////////////////////////////////////////////////////

#define ETHERNET_HS 14  // octets
header ethernet_h {
    bit<48> dst_addr;
    bit<48> src_addr;
    bit<16> ether_type;
}

#define IPV4_HS 20  // octets
header ipv4_h {
    bit<4>  version;
    bit<4>  ihl;
    bit<6>  dscp;
    bit<2>  ecn;
    bit<16> total_length;
    bit<16> identification;
    bit<3>  flags;
    bit<13> fragment_offset;
    bit<8>  ttl;
    bit<8>  protocol;
    bit<16> header_checksum;
    bit<32> src_addr;
    bit<32> dst_addr;
    // varbit<320> options;
}

#define TCP_HS 20  // octets
header tcp_h {
    bit<16>  src_port;
    bit<16>  dst_port;
    bit<32>  seq_no;
    bit<32>  ack_no;
    bit<4>   data_offset;
    bit<3>   res;
    bit<3>   ecn;
    bit<6>   ctrl;
    bit<16>  window;
    bit<16>  checksum;
    bit<16>  urgent_ptr;
}

#define UDP_HS 8  // octets
header udp_h {
    bit<16> src_port;
    bit<16> dst_port;
    bit<16> len;
    bit<16> checksum;
    bit<32> net_state;
}

// FELIX STANDALONE HEADER
#define FELIX_HS 24  // octets
header felix_h {
    bit<32> new_net_state;
    bit<32> announcer;
    bit<32> opposite;
    bit<32> prev_net_state;
    bit<32> latent_net_state;
    bit<32> n_transitions;
    // bit<240> unused;
}

struct headers {
    ethernet_h          ethernet;
    felix_h             felix;
    ipv4_h              ipv4;
    tcp_h               tcp;
    udp_h               udp;
}

struct custom_metadata_t {
    bit<16> l4_src_port;
    bit<16> l4_dst_port;
    bit<32> loc_state;
    bit<32> net_state;
    bit<32> prev_loc_state;
    bit<32> loc_state_change;
    bit<32> new_net_state;
    bit<32> prev_net_state;
    bit<32> latent_net_state;
    bit<32> n_transitions;
    bit<48> last_loc_state_change;
    bit<1>  send_notif;
    bit<1>  prop_notif;
    bit<1>  updt_notif;
    bit<32> dst_node;
    bit<32> opposite;
    bit<32> node_id;
}

////////////////////////////////////////////////////////////////
////////               PARSER DEFINITIONS               ////////
////////////////////////////////////////////////////////////////
#define ET_IPV4 0x0800
#define ET_FELIX 0x88B5
#define IP_PROTO_TCP 6
#define IP_PROTO_UDP 17

parser ParserImpl(packet_in pkt, out headers hdrs, inout custom_metadata_t cmd, 
                  inout standard_metadata_t smd) {
    state start {
        pkt.extract(hdrs.ethernet);
        transition select(hdrs.ethernet.ether_type) {
            ET_FELIX: parse_felix;
            ET_IPV4: parse_ipv4;
            default: accept;
        }
    }

    state parse_felix {
        pkt.extract(hdrs.felix);
        transition accept;
    }

    state parse_ipv4 {
        pkt.extract(hdrs.ipv4);
        transition select(hdrs.ipv4.protocol) {
            IP_PROTO_TCP: parse_tcp;
            IP_PROTO_UDP: parse_udp;
            default: accept;
        }
    }

    state parse_tcp {
        pkt.extract(hdrs.tcp);
        cmd.l4_src_port = hdrs.tcp.src_port;
        cmd.l4_dst_port = hdrs.tcp.dst_port;
        transition accept;
    }

    state parse_udp {
        pkt.extract(hdrs.udp);
        cmd.l4_src_port = hdrs.udp.src_port;
        cmd.l4_dst_port = hdrs.udp.dst_port;
        transition accept;
    }
}

////////////////////////////////////////////////////////////////
////////                   PIPELINES                    ////////
////////////////////////////////////////////////////////////////

control verifyChecksum(inout headers hdrs, inout custom_metadata_t cmd) {
    apply {
        verify_checksum(
            hdrs.ipv4.isValid(),
            {
                hdrs.ipv4.version,
                hdrs.ipv4.ihl,
                hdrs.ipv4.dscp,
                hdrs.ipv4.ecn,
                hdrs.ipv4.total_length,
                hdrs.ipv4.identification,
                hdrs.ipv4.flags,
                hdrs.ipv4.fragment_offset,
                hdrs.ipv4.ttl,
                hdrs.ipv4.protocol,
                hdrs.ipv4.src_addr,
                hdrs.ipv4.dst_addr
            },
            hdrs.ipv4.header_checksum, 
            HashAlgorithm.csum16
        );
    }
}

control ingress(inout headers hdrs, inout custom_metadata_t cmd, 
                inout standard_metadata_t smd) {
    
    register<bit<32>>(1) loc_state;  // read-only: simulates metadata
    
    register<bit<32>>(1) node_id;
    register<bit<32>>(1) net_state;
    register<bit<32>>(1) prev_loc_state;
    register<bit<32>>(1) prev_net_state;
    register<bit<32>>(1) suspect;
    register<bit<32>>(1) latent_net_state;
    register<bit<32>>(1) n_transitions;
    register<bit<48>>(1) last_loc_state_change;

    action drop() {
        mark_to_drop(smd);
    }
    
    action_selector(HashAlgorithm.crc32, 128, 16) nrml_selector;
    action nrml_fwd(bit<9> port, bit<32> dst_node) {
        smd.egress_spec = port;
        cmd.dst_node = dst_node;
        hdrs.ipv4.ttl = hdrs.ipv4.ttl - 1;
    }
    table nrml_fwding_table {
        key = {
            // match keys
            hdrs.ipv4.dst_addr: lpm;
            // selector keys
            hdrs.ipv4.dst_addr: selector;
            // hdrs.ipv4.dscp: selector;
            // hdrs.ipv4.ecn: selector;
            // hdrs.ipv4.identification: selector;
            // hdrs.ipv4.src_addr: selector;
            // hdrs.ipv4.protocol: selector;
            // cmd.l4_src_port: selector;
            // cmd.l4_dst_port: selector;
            smd.ingress_port: selector;
        }
        actions = {
            nrml_fwd;
            drop;
        }
        implementation = nrml_selector;
        @name("nrml_fwding_table_counter")
        counters = direct_counter(CounterType.packets_and_bytes);
    }

    action_selector(HashAlgorithm.crc32, 128, 16) alt_selector;
    action alt_fwd(bit<9> port) {
        smd.egress_spec = port;
    }
    table alt_fwding_table {
        key = {
            // match keys
            cmd.net_state: exact;
            cmd.dst_node: exact;
            // selector keys
            hdrs.ipv4.dst_addr: selector;
            // hdrs.ipv4.src_addr: selector;
            // hdrs.ipv4.protocol: selector;
            // cmd.l4_src_port: selector;
            // cmd.l4_dst_port: selector;
            smd.ingress_port: selector;
        }
        actions = {
            alt_fwd;
            drop;
        }
        implementation = alt_selector;
        @name("alt_fwding_table_counter")
        counters = direct_counter(CounterType.packets_and_bytes);
    }
    
    action set_opposite(bit<32> opposite) {
        cmd.opposite = opposite;
    }
    table opposite_table {
        key = {
            cmd.loc_state_change: exact;
        }
        actions = {
            set_opposite;
        }
        @name("opposite_table_counter")
        counters = direct_counter(CounterType.packets_and_bytes);
    }

    action set_new_net_state(bit<32> new_net_state, bit<32> lat_net_state) {
        cmd.new_net_state = new_net_state;
        cmd.latent_net_state = lat_net_state;
    }
    table state_transition_table {
        key = {
            cmd.net_state: exact;
            cmd.opposite: exact;
        }
        actions = {
            set_new_net_state;
        }
        @name("state_transition_table_counter")
        counters = direct_counter(CounterType.packets_and_bytes);
    }

    ///////////////////////////////////////////////////////////////
    ////////          INGRESS PIPELINE APPLY BLOCK         ////////
    ///////////////////////////////////////////////////////////////
    apply {
        node_id.read(cmd.node_id, 0);

        if(IS_NORMAL(smd)) {
            net_state.read(cmd.net_state, 0);
            n_transitions.read(cmd.n_transitions, 0);
            cmd.new_net_state = cmd.net_state;
            if(hdrs.felix.isValid()) {
                prev_net_state.read(cmd.prev_net_state, 0);
                if ((hdrs.felix.announcer != cmd.node_id)
                        && (hdrs.felix.new_net_state != cmd.net_state)
                        && (hdrs.felix.new_net_state != cmd.prev_net_state)
                        && (hdrs.felix.n_transitions >= cmd.n_transitions)) {
                    cmd.prop_notif = 1;
                    suspect.read(cmd.opposite, 0);
                    latent_net_state.read(cmd.latent_net_state, 0);
                    last_loc_state_change.read(cmd.last_loc_state_change, 0);
                    bit<48> delta = smd.ingress_global_timestamp - cmd.last_loc_state_change;
                    if((delta <= DELTA_TH) && (cmd.opposite != 0)
                            && (cmd.opposite == hdrs.felix.opposite)
                            && (cmd.latent_net_state != hdrs.felix.new_net_state)) {
                        cmd.updt_notif = 1;
                        cmd.opposite = 0;
                        cmd.new_net_state = cmd.latent_net_state;
                        cmd.n_transitions = cmd.n_transitions + 1;
                        hdrs.felix.new_net_state = cmd.latent_net_state;
                        hdrs.felix.announcer = cmd.node_id;
                        hdrs.felix.opposite = cmd.opposite;
                        hdrs.felix.prev_net_state = cmd.net_state;
                        hdrs.felix.latent_net_state = cmd.latent_net_state;
                        hdrs.felix.n_transitions = cmd.n_transitions;
                    } else if((hdrs.felix.n_transitions > cmd.n_transitions)
                            || ((hdrs.felix.n_transitions == cmd.n_transitions)
                            && (cmd.net_state > hdrs.felix.new_net_state))) {
                        cmd.new_net_state = hdrs.felix.new_net_state;
                        cmd.n_transitions = hdrs.felix.n_transitions;
                        cmd.opposite = 0;
                        cmd.latent_net_state = 0;
                    } else {
                        cmd.prop_notif = 0;
                    }
                } else {
                    drop();
                }
            } else if(hdrs.ipv4.isValid() && hdrs.ipv4.ttl > 0) {
                loc_state.read(cmd.loc_state, 0);  // "metadata access"
                prev_loc_state.read(cmd.prev_loc_state, 0);
                if (cmd.prev_loc_state != cmd.loc_state) {
                    prev_loc_state.write(0, cmd.loc_state);
                    last_loc_state_change.write(0, smd.ingress_global_timestamp);
                    cmd.send_notif = 1;
                    if(cmd.prev_loc_state == 0) {
                        cmd.new_net_state = 0;
                        cmd.opposite = 0;
                    } else {
                        cmd.loc_state_change = cmd.prev_loc_state & (~cmd.loc_state);
                        opposite_table.apply();
                        state_transition_table.apply();
                        cmd.n_transitions = cmd.n_transitions + 1;
                    }
                    clone3(CloneType.I2E, CPU_PORT, {cmd});
                }
            }
            if (cmd.new_net_state != cmd.net_state) {
                // Previous Net State
                prev_net_state.write(0, cmd.net_state);
                cmd.prev_net_state = cmd.net_state;
                //  Current Net State
                net_state.write(0, cmd.new_net_state);
                cmd.net_state = cmd.new_net_state;
                // Latent Net State
                latent_net_state.write(0, cmd.latent_net_state);
                // Suspect
                suspect.write(0, cmd.opposite);
                // Number of net state transitions
                n_transitions.write(0, cmd.n_transitions);
            }

            if (hdrs.ipv4.isValid() && hdrs.ipv4.ttl > 0) {
                nrml_fwding_table.apply();
                if (cmd.net_state > 0) {
                    alt_fwding_table.apply();
                }
                if (hdrs.udp.isValid()) {
                    // if (hdrs.udp.net_state < cmd.node_id || hdrs.ipv4.ttl == 63) {
                    hdrs.udp.net_state = cmd.net_state;
                    // }
                }
                if(hdrs.ipv4.ttl == 0) {
                    drop();
                }
            } else if (hdrs.felix.isValid()) {
                // Nothing to do here.
                // Table notification_fwding_table will be applied afterwards.
            } else {
                drop();
            }
        }
        
        if(IS_RECIRCULATED(smd)) {
            cmd.send_notif = 0;
            cmd.prop_notif = 1;
            clone(CloneType.I2E, CPU_PORT);
        }
        
        if (hdrs.felix.isValid()) {
            if (cmd.prop_notif == 1 && cmd.updt_notif == 1) {
                smd.mcast_grp = BROADCAST_MC_GRP;  // Includes a copy to the controller
            } else if (cmd.prop_notif == 1) {
                smd.mcast_grp = SELECT_MC_GRP;  // Does not include a copy to the controller
            } else {
                drop();
            }
        }
    }
}

control egress(inout headers hdrs, inout custom_metadata_t cmd, 
               inout standard_metadata_t smd) {

    action drop() {
        mark_to_drop(smd);
    }

    action rewrite_mac_addrs(bit<48> src, bit<48> dst) {
        hdrs.ethernet.src_addr = src;
        hdrs.ethernet.dst_addr = dst;
    }
    table mac_addrs {
        key = {
            smd.egress_port: exact;
        }
        actions = {
            NoAction;
            rewrite_mac_addrs;
        }
        default_action = NoAction();
    }

    ///////////////////////////////////////////////////////////////
    ////////          EGRESS PIPELINE APPLY BLOCK          ////////
    ///////////////////////////////////////////////////////////////
    apply {
        if(smd.egress_port != 0) {
            mac_addrs.apply();

            if(IS_I2E_CLONE(smd) && cmd.send_notif == 1) {
                hdrs.ipv4.setInvalid();
                hdrs.tcp.setInvalid();
                hdrs.udp.setInvalid();
                hdrs.ethernet.ether_type = ET_FELIX;

                hdrs.felix.setValid();
                hdrs.felix.new_net_state = cmd.new_net_state;
                hdrs.felix.announcer = cmd.node_id;
                hdrs.felix.opposite = cmd.opposite;
                hdrs.felix.prev_net_state = cmd.prev_net_state;
                hdrs.felix.latent_net_state = cmd.latent_net_state;
                hdrs.felix.n_transitions = cmd.n_transitions;
                // hdrs.felix.unused = 0;
                truncate(ETHERNET_HS + FELIX_HS);

                if(cmd.new_net_state > 0) {
                    recirculate({cmd});
                }
            }
        } else {
            drop();
        }
    }
}

control computeChecksum(inout headers hdrs, inout custom_metadata_t cmd) {
    apply {
        update_checksum(
            hdrs.ipv4.isValid(),
            {
                hdrs.ipv4.version,
                hdrs.ipv4.ihl,
                hdrs.ipv4.dscp,
                hdrs.ipv4.ecn,
                hdrs.ipv4.total_length,
                hdrs.ipv4.identification,
                hdrs.ipv4.flags,
                hdrs.ipv4.fragment_offset,
                hdrs.ipv4.ttl,
                hdrs.ipv4.protocol,
                hdrs.ipv4.src_addr,
                hdrs.ipv4.dst_addr
            },
            hdrs.ipv4.header_checksum, 
            HashAlgorithm.csum16
        );
    }
}

control DeparserImpl(packet_out pkt, in headers hdrs) {
    apply {
        pkt.emit(hdrs.ethernet);
        pkt.emit(hdrs.felix);
        pkt.emit(hdrs.ipv4);
        pkt.emit(hdrs.udp);
        pkt.emit(hdrs.tcp);
    }
}

V1Switch(
    ParserImpl(),
    verifyChecksum(),
    ingress(),
    egress(),
    computeChecksum(),
    DeparserImpl()
)main;