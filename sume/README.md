# Felix SUME

Felix Prototype for the [AMD/Xilinx NetFPGA-SUME Board](https://www.xilinx.com/products/boards-and-kits/1-6ogkf5.html).

## Environment Setup

This repository provides a [P4-NetFPGA-live](https://github.com/NetFPGA/P4-NetFPGA-live) project to compile the Felix P4 program. See the following link for documentation and for instructions on setting up the environment: https://github.com/NetFPGA/P4-NetFPGA-public/wiki.

## Performance Evaluation

To reproduce our performance evaluation of "Packet Processing Resources", first copy the `felix` directory in this repository to inside the path `contrib-projects/sume-sdnet-switch/projects` inside the P4-NetFPGA-live repository. Next, please follow the instructions in the following wiki https://github.com/NetFPGA/P4-NetFPGA-public/wiki/Workflow-Overview, up to "Step 10. Compile the bitstream". After these steps, resource usage reports can be generate in the command line using the following commands, inside the project directory.
```
open_project hw/project/simple_sume_switch.xpr
open_run impl_1
report_utilization -hierarchical -file hierarchical_report.txt
```

The report obtained in our evaluation is available as the file `hierarchical-resource-usage-report.txt`.