# Felix Performance and Scalability

Jupyter notebooks and scripts for the performance and scalability evaluation of Felix.

## Environment Setup

These notebooks and scripts require the installation of Python3 and a few packages. The necessary packages are listed next, please refer to the following links for documentation on installing Python 3 (and packages) on your specific operating system: [Install Python 3](https://www.python.org/downloads/) and [Installing Python3 Packages](https://packaging.python.org/en/latest/tutorials/installing-packages/).
- [NetworkX](https://networkx.org/documentation/stable/install.html)
- [Scapy](https://scapy.readthedocs.io/en/latest/installation.html)
- [NumPy](https://numpy.org/install/)
- [Pandas](https://pandas.pydata.org/getting_started.html)
- [Matplotlib](https://matplotlib.org/stable/)
- [JupyterLab or Jupyter Notebook](https://jupyter.org/install)

## Reproducing the Evaluation

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