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
}

// CLASSIC FAILURE HEADER
#define CLASSIC_HS 12  // octets
header classic_h {
    bit<32> announcer;
    bit<32> new_loc_state;
    bit<32> prev_loc_state;
}

struct headers {
    ethernet_h          ethernet;
    classic_h           classic;
    ipv4_h              ipv4;
    tcp_h               tcp;
    udp_h               udp;
}

struct custom_metadata_t {
    bit<16> l4_src_port;
    bit<16> l4_dst_port;
    bit<32> loc_state;
    bit<32> prev_loc_state;
    bit<1>  send_notif;
    bit<32> node_id;
}

////////////////////////////////////////////////////////////////
////////               PARSER DEFINITIONS               ////////
////////////////////////////////////////////////////////////////
#define ET_IPV4 0x0800
#define ET_CLASSIC 0x88B5
#define IP_PROTO_TCP 6
#define IP_PROTO_UDP 17

parser ParserImpl(packet_in pkt, out headers hdrs, inout custom_metadata_t cmd, 
                  inout standard_metadata_t smd) {
    state start {
        pkt.extract(hdrs.ethernet);
        transition select(hdrs.ethernet.ether_type) {
            ET_CLASSIC: parse_classic;
            ET_IPV4: parse_ipv4;
            default: accept;
        }
    }

    state parse_classic {
        pkt.extract(hdrs.classic);
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
    register<bit<32>>(1) prev_loc_state;
    
    action drop() {
        mark_to_drop(smd);
    }
    
    action_selector(HashAlgorithm.crc32, 128, 16) nrml_selector;
    action nrml_fwd(bit<9> port) {
        smd.egress_spec = port;
        hdrs.ipv4.ttl = hdrs.ipv4.ttl - 1;
    }
    table nrml_fwding_table {
        key = {
            // match keys
            hdrs.ipv4.dst_addr: lpm;
            // selector keys
            hdrs.ipv4.dst_addr: selector;
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

    ///////////////////////////////////////////////////////////////
    ////////          INGRESS PIPELINE APPLY BLOCK         ////////
    ///////////////////////////////////////////////////////////////
    apply {
        node_id.read(cmd.node_id, 0);

        if(IS_NORMAL(smd)) {
            if(hdrs.classic.isValid()) {
                drop();
            } else if(hdrs.ipv4.isValid() && hdrs.ipv4.ttl > 0) {
                loc_state.read(cmd.loc_state, 0);  // "metadata access"
                prev_loc_state.read(cmd.prev_loc_state, 0);
                if (cmd.prev_loc_state != cmd.loc_state) {
                    prev_loc_state.write(0, cmd.loc_state);
                    cmd.send_notif = 1;
                    clone3(CloneType.I2E, CPU_PORT, {cmd});
                }
                nrml_fwding_table.apply();
                if(hdrs.ipv4.ttl == 0) {
                    drop();
                }
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
                hdrs.ethernet.ether_type = ET_CLASSIC;

                hdrs.classic.setValid();
                hdrs.classic.announcer = cmd.node_id;
                hdrs.classic.new_loc_state = cmd.loc_state;
                hdrs.classic.prev_loc_state = cmd.prev_loc_state;
                truncate(ETHERNET_HS + CLASSIC_HS);
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
        pkt.emit(hdrs.classic);
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