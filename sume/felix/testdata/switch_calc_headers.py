#
# Copyright (c) 2020 Jonatas Adilson Marques
# All rights reserved.
#
# Copyright (c) 2017 Stephen Ibanez
# All rights reserved.
#
# This software was developed by Stanford University and the University of Cambridge Computer Laboratory 
# under National Science Foundation under Grant No. CNS-0855268,
# the University of Cambridge Computer Laboratory under EPSRC INTERNET Project EP/H040536/1 and
# by the University of Cambridge Computer Laboratory under DARPA/AFRL contract FA8750-11-C-0249 ("MRC2"), 
# as part of the DARPA MRC research programme.
#
# @NETFPGA_LICENSE_HEADER_START@
#
# Licensed to NetFPGA C.I.C. (NetFPGA) under one or more contributor
# license agreements.  See the NOTICE file distributed with this work for
# additional information regarding copyright ownership.  NetFPGA licenses this
# file to you under the NetFPGA Hardware-Software License, Version 1.0 (the
# "License"); you may not use this file except in compliance with the
# License.  You may obtain a copy of the License at:
#
#   http://www.netfpga-cic.org
#
# Unless required by applicable law or agreed to in writing, Work distributed
# under the License is distributed on an "AS IS" BASIS, WITHOUT WARRANTIES OR
# CONDITIONS OF ANY KIND, either express or implied.  See the License for the
# specific language governing permissions and limitations under the License.
#
# @NETFPGA_LICENSE_HEADER_END@
#


from scapy.all import *
import sys, os

# CALC_TYPE = 0x1212
INTSIGHT_TYPE = 0x1213

# ADD_OP     =  0
# SUB_OP     =  1
# LOOKUP_OP  =  2
# ADD_REG_OP =  3
# SET_REG_OP =  4

# class Calc(Packet):
#     name = "Calc"
#     fields_desc = [
#         IntField("op1", 0),
#         ByteEnumField("opCode", 0, {ADD_OP:"ADD", SUB_OP:"SUB", LOOKUP_OP:"LOOKUP", ADD_REG_OP:"ADD_REG", SET_REG_OP:"SET_REG"}),
#         IntField("op2", 0),
#         IntField("result", 0)
#     ]
#     def mysummary(self):
#         return self.sprintf("op1=%op1% %opCode% op2=%op2% result=%result%")

# bind_layers(Ether, Calc, type=CALC_TYPE)
# bind_layers(Calc, Raw)

class IntSight(Packet):
    name = "IntSight"
    fields_desc = [
        IntField("epoch", 0),
        BitField("path_src", 0, 8),
        BitField("path_length", 0, 8),
        BitField("path_code", 0, 8),
        BitField("contention_points", 0, 8),
        ShortField("e2e_delay", 0),
        ShortField("ingress_packets", 0),
        ShortField("ingress_bytes", 0),
        IntField("next_header", 0)
    ]
    def mysummary(self):
        return self.sprintf("epoch=%epoch% path_src=%path_src% path_len=%path_length% cps=%contention_points% e2e_delay=%e2e_delay% rxpkts=%ingress_packets% rxbytes=%ingress_bytes% next=%next_header%")

bind_layers(Ether, IntSight, type=INTSIGHT_TYPE)
bind_layers(IntSight, Raw)

class Digest(Packet):
    name = 'ISDigest'
    fields_desc = [
        LEIntField("epoch", 0),
        ByteField("flow_ID", 0),
        ByteField("path_src", 0),
        ByteField("path_length", 0),
        ByteField("path_code", 0),
        ByteField("path_dst", 0),
        ByteField("contention_points", 0),
        LEShortField("high_delays", 0),
        LEShortField("rxpkts", 0),
        LEShortField("rxbytes", 0),
        LEShortField("txpkts", 0),
        LEShortField("txbytes", 0),
        LEShortField("drops", 0),
        BitField("unused", 0, 80)
    ]
    def mysummary(self):
        return self.sprintf("epoch=%epoch% flow_ID=%flow_ID% path_src=%path_src% path_len=%path_length% path_dst=%path_dst% cps=%contention_points% high_delays=%high_delays% rxpkts=%rxpkts% rxbytes=%rxbytes% txpkts=%txpkts% txbytes=%txbytes% drops=%drops%")

bind_layers(Digest, Raw)
