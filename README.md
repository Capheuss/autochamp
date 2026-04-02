# AutoChamp

AutoChamp is a tool for automating the building, launching, and result collection of [ChampSim](https://github.com/ChampSim/ChampSim) simulations. It supports launching large numbers of simulations across multiple binaries and workloads, organizing outputs by date and run index, and scraping statistics from ChampSim's JSON output.

This fork is configured for use on **TACC Lonestar6** with SLURM job submission.

> **Disclaimer:** This infrastructure is currently untested across the full range of environments ChampSim may be used in. Please open issues for any bugs encountered and submit pull requests as needed.

---

## Repository Structure

```
autochamp/
├── auto-champ.py              # Main entry point
├── autochamp-config.cfg       # Configuration file (fill this out before use)
├── binary_list.txt            # List of binaries to launch
├── build_list.txt             # List of configurations to build
├── cvp_subset.txt             # Workload list (CVP trace subset)
├── to_collect.txt             # Stats fields to scrape from JSON output
└── champc_lib/
    ├── build.py               # ChampSim build logic
    ├── launch.py              # Job launch logic (local and SLURM)
    ├── launch_template_new.txt # SLURM job template (Lonestar6 format)
    ├── collector.py           # Statistics collection logic
    ├── config_env.py          # Configuration loading and validation
    └── utils.py               # Shared utilities
```

---

## Setup

### 1. Install AutoChamp into ChampSim

AutoChamp is intended to live inside the ChampSim directory:

```bash
cd ChampSim
git submodule update --init
```

### 2. Configure AutoChamp

Open `autochamp/autochamp-config.cfg` and fill out the required fields. Key fields are described below.

#### Job File Generation (SLURM / Lonestar6)

| Field | Description |
|---|---|
| `username` | Your TACC username — used for `squeue` job load checks |
| `job_limit` | Maximum number of concurrently queued jobs |
| `limit_hours` | Wall clock time limit per job (hours) |
| `ntasks` | Number of MPI tasks (typically `1` for serial jobs) |
| `partition` | SLURM queue/partition (e.g. `normal`, `development`, `gpu`) |
| `account` | TACC allocation name to charge |
| `mail` | Email address for job notifications |
| `num_cores` | Number of cores per simulation |
| `launch_file` | Path where temporary job files are written before submission |
| `launch_template` | Path to the SLURM job template file |

#### Simulation Parameters

| Field | Description |
|---|---|
| `HPRC` | `1` to submit via SLURM, `0` to run locally |
| `enable_json_output` | `1` to pass `--json` flag to ChampSim (required for `--collect`) |
| `warmup` | Number of warmup instructions |
| `sim_inst` | Number of simulation instructions |
| `binaries_path` | Path to the compiled ChampSim binaries |
| `results_path` | Root directory where simulation outputs are written |
| `workload_path` | Directory containing trace files |
| `binary_list` | File listing which binaries to run |
| `workload_list` | File listing which traces to run |

#### Statistics Collection

| Field | Description |
|---|---|
| `results_collect_path` | Path to the results directory to scrape |
| `stats_list` | File describing which JSON fields to collect |
| `baseline` | *(Optional)* Binary name to use as IPC baseline for comparisons |

---

## Usage

All commands are run from the ChampSim directory using:

```bash
python3 autochamp/auto-champ.py -f autochamp/autochamp-config.cfg [OPTIONS]
```

### Options

| Flag | Description |
|---|---|
| `-f`, `--config` | Path to the configuration file (required) |
| `-b`, `--build` | Build ChampSim binaries from configurations in `build_list` |
| `-l`, `--launch` | Launch simulations for all binary/workload combinations |
| `-c`, `--collect` | Collect statistics from simulation JSON outputs |
| `-p`, `--print_stats` | Print the available JSON stat fields without scraping |
| `-y`, `--yall` | Automatically confirm all prompts (use with caution) |

### Build

```bash
python3 autochamp/auto-champ.py -f autochamp/autochamp-config.cfg -b
```

Requires `build_list` and `configs_path` to be set in the config.

### Launch

```bash
python3 autochamp/auto-champ.py -f autochamp/autochamp-config.cfg -l
```

With `HPRC = 1`, generates a SLURM job file from `launch_template.txt` for each binary/workload pair and submits it via `sbatch`. AutoChamp monitors the queue and throttles submission once `job_limit` is reached, polling every 30 seconds.

### Collect

```bash
python3 autochamp/auto-champ.py -f autochamp/autochamp-config.cfg -c
```

Scrapes statistics defined in `stats_list` from ChampSim's JSON output files. Run with `-p` first to explore available fields:

```bash
python3 autochamp/auto-champ.py -f autochamp/autochamp-config.cfg -c -p
```

---

## Results Structure

Simulation outputs are organized under `results_path` by date and sequential run index:

```
results/
└── YYYY-MM-DD/
    └── 1_cores/
        ├── 1/    # First launch set of the day
        ├── 2/    # Second launch set of the day
        └── ...
```

> **Note:** Simulations launched overnight will have their outputs placed in a folder for the new date.
