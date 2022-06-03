# IntSight

IntSight Prototype for Mininet + BMv2.

## Environment Setup

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

## Running Experiments

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