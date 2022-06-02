//
// Copyright (c) 2020 Jonatas Adilson Marques
// All rights reserved.
//
// This software was developed by Stanford University and the University of Cambridge Computer Laboratory 
// under National Science Foundation under Grant No. CNS-0855268,
// the University of Cambridge Computer Laboratory under EPSRC INTERNET Project EP/H040536/1 and
// by the University of Cambridge Computer Laboratory under DARPA/AFRL contract FA8750-11-C-0249 ("MRC2"), 
// as part of the DARPA MRC research programme.
//
// @NETFPGA_LICENSE_HEADER_START@
//
// Licensed to NetFPGA C.I.C. (NetFPGA) under one or more contributor
// license agreements.  See the NOTICE file distributed with this work for
// additional information regarding copyright ownership.  NetFPGA licenses this
// file to you under the NetFPGA Hardware-Software License, Version 1.0 (the
// "License"); you may not use this file except in compliance with the
// License.  You may obtain a copy of the License at:
//
//   http://www.netfpga-cic.org
//
// Unless required by applicable law or agreed to in writing, Work distributed
// under the License is distributed on an "AS IS" BASIS, WITHOUT WARRANTIES OR
// CONDITIONS OF ANY KIND, either express or implied.  See the License for the
// specific language governing permissions and limitations under the License.
//
// @NETFPGA_LICENSE_HEADER_END@
//


#include <core.p4>
#include <sume_switch.p4>

typedef bit<48> EthAddr_t;
typedef bit<32> IPv4Addr_t;
#define IPV4_TYPE 0x0800
#define UPDATE_TYPE 0x1212
#define FELIX_TYPE 0x1213
#define INDEX_WIDTH 1
#define MAX_LATENCY 1024
#define THRESHOLD 10

#define REG_READ 8w0
#define REG_WRITE 8w1
#define REG_ADD  8w2
#define REG_BOR  8w2

#define EQ_RELOP    8w0
#define NEQ_RELOP   8w1
#define GT_RELOP    8w2
#define LT_RELOP    8w3

// Extern: Get Timestamp
@Xilinx_MaxLatency(MAX_LATENCY)
@Xilinx_ControlWidth(0)
extern void get_timestamp(in bit<1> valid, out bit<32> result);

// Register: Tactic
@Xilinx_MaxLatency(MAX_LATENCY)
@Xilinx_ControlWidth(INDEX_WIDTH)
extern void tactic_reg_rw(in  bit<INDEX_WIDTH> index,
                          in  bit<32>   newVal,
                          in  bit<8>    opCode,
                          out bit<32>   result);

// Register: Number of Transitions
@Xilinx_MaxLatency(MAX_LATENCY)
@Xilinx_ControlWidth(INDEX_WIDTH)
extern void ntransitions_reg_rw(in  bit<INDEX_WIDTH> index,
                                in  bit<32>   newVal,
                                in  bit<8>    opCode,
                                out bit<32>   result);

// Register: Last Transition Timestamp
@Xilinx_MaxLatency(MAX_LATENCY)
@Xilinx_ControlWidth(INDEX_WIDTH)
extern void transitionts_reg_rw(in  bit<INDEX_WIDTH> index,
                                in  bit<32>   newVal,
                                in  bit<8>    opCode,
                                out bit<32>   result);

// Register: Last Port Status
@Xilinx_MaxLatency(MAX_LATENCY)
@Xilinx_ControlWidth(INDEX_WIDTH)
extern void portstatus_reg_praw(in  bit<INDEX_WIDTH> index,
                                in  bit<32>   newVal,
                                in  bit<32>   incVal,
                                in  bit<8>    opCode,
                                in  bit<32>   compVal,
                                in  bit<8>    relOp,
                                out bit<32>   result,
                                out bit<1>    boolean);


// standard Ethernet header
header Ethernet_h { 
    EthAddr_t dstAddr; 
    EthAddr_t srcAddr; 
    bit<16> etherType;
}

// IPv4 header without options
header IPv4_h {
    bit<4> version;
    bit<4> ihl;
    bit<8> tos;
    bit<16> totalLen;
    bit<16> identification;
    bit<3> flags;
    bit<13> fragOffset;
    bit<8> ttl;
    bit<8> protocol;
    bit<16> hdrChecksum;
    IPv4Addr_t srcAddr;
    IPv4Addr_t dstAddr;
}

header Felix_notification_h {
    bit<32> new_tactic;
    bit<32> ntransitions;
    bit<32> transitionts;
    bit<32> element;
    bit<32> announcer;
}

header Felix_update_h {
    bit<32> new_tactic;
    bit<32> ntransitions;
    bit<32> transitionts;
    bit<32> element;
}

// List of all recognized headers
struct Parsed_packet { 
    Ethernet_h ethernet;
    IPv4_h ip;
    Felix_notification_h felix;
    Felix_update_h update;
}

// user defined metadata: can be used to share information between
// TopParser, TopPipe, and TopDeparser 
struct user_metadata_t {
    bit<32> port_status;
    bit<32> tactic;
    bit<32> ntransitions;
    bit<32> transitionts;
    bit<32> element;
    bit<32> dst_node;
}

// digest_data, MUST be 256 bits
struct digest_data_t {
    bit<256>    unused;
}

// Parser Implementation
@Xilinx_MaxPacketRegion(1024)
parser TopParser(packet_in b, 
                 out Parsed_packet p, 
                 out user_metadata_t user_metadata,
                 out digest_data_t digest_data,
                 inout sume_metadata_t sume_metadata) {
    
    state start {
        b.extract(p.ethernet);
        user_metadata.port_status = 0;
        user_metadata.tactic = 0;
        user_metadata.ntransitions = 0;
        user_metadata.transitionts = 0;
        user_metadata.element = 0;
        user_metadata.dst_node = 0;
        digest_data.unused = 0;

        transition select(p.ethernet.etherType) {
            IPV4_TYPE: parse_ipv4;
            UPDATE_TYPE: parse_update;
            FELIX_TYPE: parse_felix;
            default: reject;
        } 
    }

    state parse_ipv4 {
        b.extract(p.ip);
        transition accept;
    }

    state parse_update {
        b.extract(p.update);
        transition accept;
    }

    state parse_felix {
        b.extract(p.felix);
        transition accept;
    }
}

// match-action pipeline
control TopPipe(inout Parsed_packet p,
                inout user_metadata_t user_metadata, 
                inout digest_data_t digest_data,
                inout sume_metadata_t sume_metadata) {

    action set_dst_port(port_t port, bit<32> dst_node) {
        sume_metadata.dst_port = port;
        user_metadata.dst_node = dst_node;
    }

    table ipv4_forward {
        key = { p.ip.dstAddr : exact; }
        actions = {
            set_dst_port;
            NoAction;
        }
        size = 64;
        default_action = NoAction;
    }

    action alt_dst_port(port_t port) {
        sume_metadata.dst_port = port;
    }

    table alt_forward {
        key = { 
            user_metadata.tactic : exact;
            user_metadata.dst_node : exact;
        }
        actions = {
            alt_dst_port;
            NoAction;
        }
        size = 64;
        default_action = NoAction;
    }

    action set_element(bit<32> element) {
        user_metadata.element = element;
    }

    table element {
        key = {
            user_metadata.port_status : exact;
        }
        actions = {
            set_element;
            NoAction;
        }
        size = 64;
        default_action = NoAction;
    }

    action transition_tactics(bit<32> new_tactic, bit<32> ntransitionsInc) {
        user_metadata.tactic = new_tactic;
        user_metadata.ntransitions = user_metadata.ntransitions + ntransitionsInc;
    }

    table tactics {
        key = {
            user_metadata.tactic : exact;
            user_metadata.element : exact;
        }
        actions = {
            transition_tactics;
            NoAction;
        }
        size = 64;
        default_action = NoAction;
    }

    action transition_sftactics(bit<32> new_tactic, bit<32> ntransitionsInc) {
        user_metadata.tactic = new_tactic;
        user_metadata.ntransitions = user_metadata.ntransitions + ntransitionsInc;
        p.felix.new_tactic = new_tactic;
        p.felix.ntransitions = user_metadata.ntransitions + ntransitionsInc;
    }

    table sftactics {
        key = {
            user_metadata.tactic : exact;
            p.felix.element : exact;
        }
        actions = {
            transition_sftactics;
            NoAction;
        }
        size = 64;
        default_action = NoAction;
    }

    apply {

        if(p.ip.isValid()) {
            ipv4_forward.apply();
        }

        bit<8> opCode;
        if(p.update.isValid()) {
            opCode = REG_WRITE;
        } else {
            opCode = REG_READ;
        }
        tactic_reg_rw(
            ((bit<INDEX_WIDTH>) 0), // index
            p.update.new_tactic, // newVal
            opCode, // opCode
            user_metadata.tactic // result
        );
        ntransitions_reg_rw(
            ((bit<INDEX_WIDTH>) 0), // index
            p.update.ntransitions, // newVal
            opCode, // opCode
            user_metadata.ntransitions // result
        );
        transitionts_reg_rw(
            ((bit<INDEX_WIDTH>) 0), // index
            p.update.transitionts, // newVal
            opCode, // opCode
            user_metadata.transitionts // result
        );

        if(p.update.isValid()) {
            p.felix.setValid();
            p.felix.new_tactic = p.update.new_tactic;
            p.felix.ntransitions = p.update.ntransitions;
            p.felix.transitionts = p.update.transitionts;
            p.felix.element = p.update.element;
            p.felix.announcer = 42;
            p.update.setInvalid();
            // Multicast packet to all ports
        } else if(p.felix.isValid()) {
            if(p.felix.new_tactic == user_metadata.tactic || p.felix.ntransitions < user_metadata.ntransitions) {
                // Discard packet
            } else {
                if((p.felix.transitionts - user_metadata.transitionts) < THRESHOLD) {
                    sftactics.apply();
                }
                p.update.setValid();
                p.update.new_tactic = p.felix.new_tactic;
                p.update.ntransitions = p.felix.ntransitions;
                p.update.transitionts = p.felix.transitionts;
                p.update.element = p.felix.element;
                p.felix.setInvalid();
                // Recirculate the packet
            }
        } else if(p.ip.isValid()) {
            bit<1> port_status_changed = 0;
            portstatus_reg_praw((
                (bit<INDEX_WIDTH>) 0), // index
                user_metadata.port_status, // newVal
                0, // incVal - never used
                REG_WRITE, // opCode
                user_metadata.port_status, // compVal
                NEQ_RELOP, // relOp
                user_metadata.port_status, // result
                port_status_changed // predicate result
            );
            if(port_status_changed == 1) {
                element.apply();
                tactics.apply();
                p.update.setValid();
                p.update.new_tactic = user_metadata.tactic;
                p.update.ntransitions = user_metadata.ntransitions;
                get_timestamp(1, user_metadata.transitionts);
                p.update.transitionts = user_metadata.transitionts;
                p.update.element = user_metadata.element;
                // Recirculate the packet
            }

            // ipv4_forward.apply();
            if(user_metadata.tactic != 0) {
                alt_forward.apply();
            }
        }
    }
}

// Deparser Implementation
@Xilinx_MaxPacketRegion(1024)
control TopDeparser(packet_out b,
                    in Parsed_packet p,
                    in user_metadata_t user_metadata,
                    inout digest_data_t digest_data,
                    inout sume_metadata_t sume_metadata) { 
    apply {
        b.emit(p.ethernet);
        b.emit(p.ip);
        b.emit(p.felix);
        b.emit(p.update);
    }
}


// Instantiate the switch
SimpleSumeSwitch(TopParser(), TopPipe(), TopDeparser()) main;
