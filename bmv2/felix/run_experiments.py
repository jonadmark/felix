"""Felix Run Experiments.

Usage:
    run_experiments.py <recipe> <experiment_dir>
"""
import json
import os
import time

from datetime import datetime
from distutils.dir_util import copy_tree

from docopt import docopt


def main(recipe, exp_dir):
    # Output dir
    cdt = datetime.utcnow().strftime('D%Y-%m-%dT%H-%M-%S')
    output_dir = '../results/{}'.format(cdt)
    os.makedirs(output_dir + '/metadata')
    
    # Benchmark
    with open(recipe) as f:
        bm = json.load(f)
    with open(output_dir + '/metadata/benchmark.json', 'w') as f:
        json.dump(bm, f)

    engines = bm['engines']
    f_scenarios = bm['failure_scenarios']
    runs_pfs = bm['runs_per_failure_scenario']
    
    # Experiment Mainfile
    with open(exp_dir + '/main.json') as f:
        exp = json.load(f)
    with open(output_dir + '/metadata/experiment.json', 'w') as f:
        json.dump(exp, f)

    bwl_dir = exp['workload']['base_dir']
    with open(bwl_dir + 'build_workload_log.json') as f:
        bwl = json.load(f)
    with open(output_dir + '/metadata/build_workload_log.json', 'w') as f:
        json.dump(bwl, f)

    for fs_name, fs in f_scenarios.items():
        print('Failure Scenario:', fs_name)
        exp['network']['failures'] = fs

        with open('scenario.json', 'w') as f:
            json.dump(exp, f, indent=4)

        for run in range(runs_pfs):
            print('Run:', run)
            for engine in engines:
                print('Engine:', engine)
                
                cmd = 'bash run_experiment.sh {} scenario.json | tee /tmp/exp_log.txt'.format(engine)
                # cmd = 'bash run_experiment.sh {} scenario.json'.format(engine)
                os.system(cmd)
                os.system('cp /tmp/exp_log.txt ./logs/exp_log.txt')

                cmd = 'python3 {exp_dir}/analyze_logs.py scenario.json {bwl_dir}/build_workload_log.json ./logs/ | tee ./logs/analysis_result.txt'
                cmd = cmd.format(exp_dir=exp_dir, bwl_dir=bwl_dir)
                os.system(cmd)

                time.sleep(2)

                run_dir = output_dir + '/E{}-F{}-R{:02d}'.format(engine, fs_name, run)
                os.makedirs(run_dir)

                cmd = 'cat logs/{}_routing.txt'.format(engine)
                os.system(cmd)
                print('\n')

                copy_tree('.', run_dir)

                print('#'*80)
                print('End of Run: (E{}-F{}-R{:02d})'.format(engine, fs_name, run))
                print('#'*80)
                print('Taking a nap for 20 seconds.')
                time.sleep(20)


if __name__ == '__main__':
    args = docopt(__doc__)
    main(args['<recipe>'], args['<experiment_dir>'])