# Felix

This repository presents the prototypes and artifacts of the paper entitled "Every Packet Counts: Responding to Network
Failures at Data-plane Speeds". It contains three main directories: `bmv2`, `notebook`, and `sume`, which we present next.

## 1. BMv2
IntSight Prototype for Mininet + BMv2.

### 1.1 Environment Setup

Follow the next steps to setup an experimental environment to reproduce the experiments with Felix's BMv2 prototype. This prototype was build for and tested on Ubuntu 16.04. We recommend using this release of Ubuntu. We also recommend starting from a clean install and setting up the environment on a well provisioned baremetal machine. For the paper, we ran our experiments on a dedicated Ubuntu 16.04 (Linux 4.4) server with 2x Intel Xeon Silver 4208 2.1 GHz 8-core 16-thread processors, 8x 16 GB 2400 MHz RAM, and 2 TB of NVMe SSD storage.

Start by opening a new terminal window and navigating to the `bmv2/install` directory in this repository. Assuming the terminal in on the root directory of this repository, run:
```
cd bmv2/install
```
Install the base dependencies with the following command:
```
sudo bash install_basedeps.sh
```
Next, install the P4 environment with the following command. This may take a while to run depending on the machine resources. In our experience, it takes from about one to three hours for the script to install the P4 environment.
```
bash install_p4env.sh
```
Install a Python3 environment using the Conda open source package management system and environment management system. Make sure to opt-in for initializing and auto activating Conda when prompted during the installation process.
```
bash install_conda.sh
```
After the installation, Conda will work on all newly initiated terminal sessions. Close the session you are using and start a new one. Finally, install the necessary Python3 libraries with the following command.
```
bash install_python3libs.sh
```
The environment is all set for running the experiments!

### 1.2 Running Experiments

The first step in reproducing experiments, is chosing which experiment to run. This repository comes with two network topologies (i.e., Abilene and 4-port FatTree) and associated to each, multiple evaluation blueprints for emulating different scenarios (e.g., single link failure scenarios, no failures). We refer to a pair of topology and blueprint as an 'experiment'. These experiments are available in the path `bmv2/felix/experiments/`. For the purpose of this tutorial, we will focus on the experiment involving _single link failures_ in the _Abilene_ topology. Other experiments can be run with the equivalent commands.

We begin this tutorial, by navigating to the directory that holds the experiment we wish to run. In our case, this directory is `bmv2/felix/experiments/abilene/`. On a terminal window, type:
```
cd felix/experiments/abilene
```
Next, since our intent is to measure packet loss in the event of failures, we first need to build/prepare the traffic that the network will (try to) send during the experimentation. This can be done with the following command:
```
python3 build_workload.py main.json
```
The script above creates PCAP files with packets following traffic demands between switches in the network as defined in the configuration file `main.json` (`workload -> demands`). The PCAP files are stored in a new directory called `resources/workloads/abilene/` created inside the main bmv2 prototype directory, and will be used during the experiment to generate traffic in the network.

After the network workload traffic has been created, we can run the desired experiment with the following command inside the `bmv2/felix` directory:
```
python3 run_experiments.py ./experiments/abilene/blueprints/single_link.json ./experiments/abilene/
```
The first parameter of the script `run_experiments.py` indicates a evaluation blueprint file, and the second indicates the network directory. Next, we present the contents of the blueprint file and of the network definition file `main.json` and describe their main elements.

**File: `./experiments/abilene/blueprints/single_link.json`**
```
{
    "engines": ["felix", "classic"],
    "failure_scenarios": {
        "s1-s2": [{"delay": 0.100, "type": "link", "element": ["s1", "s2"]}],
        "s1-s3": [{"delay": 0.100, "type": "link", "element": ["s1", "s3"]}],
        "s2-s11": [{"delay": 0.100, "type": "link", "element": ["s2", "s11"]}],
        "s3-s10": [{"delay": 0.100, "type": "link", "element": ["s3", "s10"]}],
        "s4-s5": [{"delay": 0.100, "type": "link", "element": ["s4", "s5"]}],
        "s4-s7": [{"delay": 0.100, "type": "link", "element": ["s4", "s7"]}],
        "s5-s6": [{"delay": 0.100, "type": "link", "element": ["s5", "s6"]}],
        "s5-s7": [{"delay": 0.100, "type": "link", "element": ["s5", "s7"]}],
        "s6-s9": [{"delay": 0.100, "type": "link", "element": ["s6", "s9"]}],
        "s7-s8": [{"delay": 0.100, "type": "link", "element": ["s7", "s8"]}],
        "s8-s9": [{"delay": 0.100, "type": "link", "element": ["s8", "s9"]}],
        "s8-s11": [{"delay": 0.100, "type": "link", "element": ["s8", "s11"]}],
        "s9-s10": [{"delay": 0.100, "type": "link", "element": ["s9", "s10"]}],
        "s10-s11": [{"delay": 0.100, "type": "link", "element": ["s10", "s11"]}]
    },
    "runs_per_failure_scenario": 5
}
```
- `"engines"` refers to the approaches to be evaluate, `"classic"` means Standard-SDN.
- `"failure_scenarios"` refers to the failure scenarios to be considered, each one individually. The list above includes all links in the Abiline topology.
- `"runs_per_failure_scenario"` indicates the number of times to consider each pair of engine and failure scenario.

**File: `./experiments/abilene/main.json`**
```
{
    "capture_traffic": false,
    "enable_debugger": false,
    "trim_and_clear": false,
    "run_workload": true,
    "sim_failures": true,
    "slowdown": 400,
    "network": {
        "n_switches": 11,
        "hosts_per_switch": 1,
        "default_link_delay": 0,
        "control_plane_location": "s8",
        "default_link_bandwidth": 9953.280,
        "queue_rate": 2488320,
        "queue_depth": 124416,
        "entry_installation_rate": 500,
        "switch_links": [
            {"u": "s1", "v": "s2", "delay": 1913},
            {"u": "s1", "v": "s3", "delay": 552},
            {"u": "s2", "v": "s11", "delay": 443},
            {"u": "s3", "v": "s10", "delay": 1457},
            {"u": "s4", "v": "s5", "delay": 1901},
            {"u": "s4", "v": "s7", "delay": 2738},
            {"u": "s5", "v": "s6", "delay": 842},
            {"u": "s5", "v": "s7", "delay": 2509},
            {"u": "s6", "v": "s9", "delay": 3680},
            {"u": "s7", "v": "s8", "delay": 1490},
            {"u": "s8", "v": "s9", "delay": 1740},
            {"u": "s8", "v": "s11", "delay": 1221},
            {"u": "s9", "v": "s10", "delay": 1882},
            {"u": "s10", "v": "s11", "delay": 1150}
        ]
    },
    "workload": {
        "duration": 0.500,
        "base_dir": "../resources/workloads/abilene/",
        "multiplier": 0.25,
        "demands": [
            {"src": "h1", "dst": "h2", "rate": 193.388},
            [...]
            {"src": "h11", "dst": "h10", "rate": 737.612}
        ]
    }
}
```
- `"capture_traffic"` indicates whether the traffic in the network should be captured, for debugging purposes only.
- `"run_workload"` a simple switch to enable/disable actually generating traffic in the network.
- `"sim_failures"` a simple switch to enable/disable actually causing failures in the network.
- `"network"` defines the network topology. This involves defining the number of switches (and their processing capacity), hosts connected to each switch, control plane server location, and network links (and their bandwidth and latency).
- `"workload"` defines the network workload. This involes the duration of the workload, the directory where the traffic PCAPs are stored, and the demands between pairs of hosts.

After running an experiment, all results (including the number (and percentage) of packets lost) and logs are found in a new directory created in `bmv2/results/` with the name defined as the date and time of when the experiment was run. Inside this directory, one subdirectory is created for each run of each pair of failure scenario and approach with the format `"E<engine>-F<failure_scenario>-R<run_number>"`. For example, the second run for the failure scenario where link s8-s9 has failed and traffic was reroute via Felix would have its results stored in subdirectory `Efelix-Fs8-s9-R01`. Of particular interest for analysis is the log file called `logs/analysis_result.txt`, which contains the number and percentage of packet loss as well as received correctly.

Congratulations! You are all done with running an experiment and obtaining packet loss measurements.

## 2. Notebook

Jupyter notebooks and scripts for the performance and scalability evaluation of Felix.

### 2.1 Environment Setup

These notebooks and scripts require the installation of Python3 and a few packages. The necessary packages are listed next, please refer to the following links for documentation on installing Python 3 (and packages) on your specific operating system: [Install Python 3](https://www.python.org/downloads/) and [Installing Python3 Packages](https://packaging.python.org/en/latest/tutorials/installing-packages/).
- [NetworkX](https://networkx.org/documentation/stable/install.html)
- [Scapy](https://scapy.readthedocs.io/en/latest/installation.html)
- [NumPy](https://numpy.org/install/)
- [Pandas](https://pandas.pydata.org/getting_started.html)
- [Matplotlib](https://matplotlib.org/stable/)
- [JupyterLab or Jupyter Notebook](https://jupyter.org/install)

### 2.2 Reproducing the Evaluation: Downtime and Scalability

This directory contains two Python scripts and three Jupyter notebooks, which perform a hybrid measurement and analytical modelling evaluation of Felix and the related approaches to build Figures 5-7 and Table III in the paper. Script `routing.py` simulates the execution of Felix routing application and measures the time it takes to compute normal and alternative forwarding entries for the selected networks. As described in the paper, this script was ran with 30 threads on a dedicated Ubuntu 16.04 (Linux 4.4) server with 2x Intel Xeon Silver 4208 2.1 GHz 8-core 16-thread processors, 8x 16 GB 2400 MHz RAM, and 2 TB of NVMe SSD storage. This script may take considerable time to run depending on the networks under evaluation. The paper results are readily available in directory `results/routing/summary/`, which presents result files for each evaluated network. Script `detailed-n-entries.py` accounts in detail, for evaluation purposes only, the number of forwarding entries that need to be installed in each switch in the network for each failure scenario. Similar to `routing.py`, the paper results are readily available in directory `results/routing/detailed-n-entries/`, which presents result files for each evaluated network. The results of both scripts are the base for the analysis of each Jupyter Notebook. Should one desire to rerun these scripts, that can be done with the following simple comands.
```
python3 routing.py
python3 detailed-n-entries.py
```

After obtaining the results from the base scripts, the full evaluation, including the generation of figures and tables, is done with the notebooks `downtime-compute.ipynb`, `downtime-plot.ipynb`, and `scalability.ipynb`.


Notebooks `downtime-compute.ipynb` and `downtime-plot.ipynb` generate Figures 5-7 related to the performance evaluation focused on the downtime observed by the network assuming different failure recovery approaches. Namely, we consider Felix along with the two SDN-OpenFlow approaches described in the paper (Section 2): one that computes alternative forwarding entries only upon failure and another that pre-computes and caches in the control plane the forwarding entries necessary for each failure scenario. We refer to the first approach as Standard SDN (S-SDN) and to the second as Pre-Compute SDN (PC-SDN). To generate Figures 5-7, one should first run notebook `downtime-compute.ipynb` to compute the downtime for each combination of network, failure scenario, factor variation, and approach and store the results in `results/downtime/csvs/`. This script can take a while to finish (about 30 minutes in our experience). After the downtime has been computed, notebook `downtime-plot.ipynb` can then be used to generate the figures. This notebook graphically presents a myriad of information regarding downtime as a factor of the detection delay and entry installation delay, downtime speedup, as well as relative and absolute factor cost breakdown. Figure results for this second notebook are also saved to `results/downtime/figures`. These notebooks can be opened with the following commands:
```
jupyter notebook downtime-compute.ipynb
jupyter notebook downtime-plot.ipynb
```
The commands above will open one browser window for each notebook. Initially, each notebook shows a snapshot of the results presented in the paper. To reproduce the results, in the browser window, open the Kernel menu and click on Restart & Run All. This will run the notebook and generate all results and figures. Notebook `downtime-compute.ipynb` should be run before `downtime-plot.ipynb`.

Notebook `scalability.ipynb` generate Table III related to the scalability evaluation focused on: memory usage, pre-compute runtime, and notification overhead. This notebook compiles and processes the results previously obtained by scripts `routing.py` and `detailed-n-entries.py` considering various aspects of existing P4 programmable targets. Similar to the previous notebook, this one can be opened with the following command:
```
jupyter notebook scalability.ipynb
```
Again, the command above will open a browser window with the notebook showing a snapshot of the paper results. Reproducing the results takes the same steps as before, in the browser window, open the Kernel menu and click on Restart & Run All. This will run the notebook and generate the table. The table is also saved in CSV format in `results/scalability/tableIII-summary.csv`.

Congratulations! This concludes the instructions for reproducing the performance and scalability evaluations.

## 3. SUME

Felix Prototype for the [AMD/Xilinx NetFPGA-SUME Board](https://www.xilinx.com/products/boards-and-kits/1-6ogkf5.html).

### 3.1 Environment Setup

This repository provides a [P4-NetFPGA-live](https://github.com/NetFPGA/P4-NetFPGA-live) project to compile the Felix P4 program. See the following link for documentation and for instructions on setting up the environment: https://github.com/NetFPGA/P4-NetFPGA-public/wiki.

### 3.2 Reproducing the Evaluation: Packet processing resources

To reproduce our performance evaluation of "Packet Processing Resources", first copy the `felix` directory in this repository to inside the path `contrib-projects/sume-sdnet-switch/projects` inside the P4-NetFPGA-live repository. Next, please follow the instructions in the following wiki https://github.com/NetFPGA/P4-NetFPGA-public/wiki/Workflow-Overview, up to "Step 10. Compile the bitstream". After these steps, resource usage reports can be generate in the command line using the following commands, inside the project directory.
```
open_project hw/project/simple_sume_switch.xpr
open_run impl_1
report_utilization -hierarchical -file hierarchical_report.txt
```

The report obtained in our evaluation is available as the file `hierarchical-resource-usage-report.txt`.

Congratulations! This concludes the instructions for reproducing the part related to packet processing resources of the performance evaluation.