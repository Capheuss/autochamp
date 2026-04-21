import sys
import os
from datetime import date
import time 
import subprocess
import re
import champc_lib.utils as utils
import champc_lib.config_env as ce 

def check_load(env_con):
  username = env_con.fields["username"]
  job_limit = int(env_con.fields["job_limit"])
  curr_bin = env_con.fields["current_binary"]

  if env_con.fields["HPRC"]:
    procs_running = int(subprocess.check_output(f"squeue -u {username} | wc -l", stderr = subprocess.STDOUT, shell = True)) - 1
    print(time.strftime("%H:%M:%S", time.localtime()) + f" - Jobs running {str(procs_running)} Limit {str(job_limit)}")
    if procs_running < job_limit:
      return False
    else:
      time.sleep(30)
      return True
  else:
    procs_running = int(subprocess.check_output(f"ps -u {username} | grep \"{curr_bin}\" | wc -l", stderr = subprocess.STDOUT, shell = True))

    print(f"Procs running: {procs_running} Bin {curr_bin}")
    print(time.strftime("%H:%M:%S", time.localtime()) + f" - Jobs running {str(procs_running)} Limit {str(job_limit)}")

    if procs_running < job_limit:
      return False
    else:
      time.sleep(30)
      return True


def _make_dir(path):
  """Create directory (and parents) if it does not already exist."""
  os.makedirs(path, exist_ok=True)


def create_results_directory(env_con):
  """
  Create and return the simulation-results output path:
      <results_path>/<date>/<N>_cores/<run>/

  The run counter is auto-incremented so each invocation of the launcher
  gets a fresh, numbered sub-directory.
  """
  results_path = env_con.fields["results_path"]
  num_cores = str(env_con.fields["num_cores"])
  td = str(date.today())

  path_parts = [td + "/", num_cores + "_cores/"]
  count = 1
  count_str = f"{str(count)}/"

  if not os.path.isdir(os.path.join(results_path, *path_parts)):
    path_parts.append(count_str)
    _make_dir(os.path.join(results_path, *path_parts))
  else:
    while os.path.isdir(os.path.join(results_path, *path_parts, count_str)):
      count += 1
      count_str = f"{str(count)}/"
    path_parts.append(count_str)
    _make_dir(os.path.join(results_path, *path_parts))

  results_path += "".join(path_parts)
  print(f"Created results directory: {results_path}")
  return results_path, count_str.rstrip("/")   # also return the run number


def create_logs_directory(env_con, run_count_str):
  """
  Create and return the SLURM stdout/stderr log path:
      <logs_path>/<date>/<N>_cores/<run>/

  Uses the same date and run number as the results directory so logs and
  results always share the same index and are easy to correlate.
  """
  logs_path = env_con.fields["logs_path"]
  num_cores = str(env_con.fields["num_cores"])
  td = str(date.today())

  log_dir = os.path.join(logs_path, td, num_cores + "_cores", run_count_str) + "/"
  _make_dir(log_dir)
  print(f"Created logs directory:    {log_dir}")
  return log_dir


def launch_simulations(env_con, launch_str, result_str, output_name):
  """Non-HPRC local launch: redirect ChampSim stdout directly to result_str."""
  launch_str = f"{launch_str.strip()} > {result_str} &"
  print(f"Final CMD: {launch_str}")
  while check_load(env_con):
    continue
  os.system(launch_str)


def sbatch_launch(env_con, launch_str, result_str, log_str, output_name):
  """
  HPRC SLURM launch.

  result_str  — path prefix for the ChampSim output file (in results/)
  log_str     — path prefix for SLURM stdout/stderr files (in job_files/)

  The template uses {result_str} for the ChampSim redirect and {log_str}
  for the #SBATCH -o / -e directives, keeping them in separate trees.
  """
  while check_load(env_con):
    continue

  launchf = env_con.fields["launch_file"]
  temp_launch = open(launchf, "w")

  tmpl = open(env_con.fields["launch_template"], "r")

  for line in tmpl:
    matches = re.findall(r"{([^{}]*)}", line)
    out_line = line
    for match in matches:
      if match not in env_con.fields.keys() and match not in env_con.ignore_fields:
        print(f"{match}: Not defined and required for launching\n")
        exit()
      if match in env_con.ignore_fields:
        if match == "result_str":
          out_line = out_line.replace("{" + match + "}", result_str)
        elif match == "log_str":
          out_line = out_line.replace("{" + match + "}", log_str)
        elif match == "output_name":
          print(output_name)
          out_line = out_line.replace("{" + match + "}", output_name)
      else:
        out_line = out_line.replace("{" + match + "}", env_con.fields[match])

    temp_launch.write(out_line.strip() + "\n")

  temp_launch.write(launch_str)
  temp_launch.close()

  print(f"Running command: sbatch {launchf}")
  os.system(f"sbatch {launchf}")
  os.system(f"rm {launchf}")


def launch_handler(env_con):

  binaries  = []
  workloads = []

  with open(env_con.fields["binary_list"], "r") as binary_list_file:
    binaries = list(utils.filter_comments_and_blanks(binary_list_file))

  with open(env_con.fields["workload_list"], "r") as workloads_list_file:
    workloads = list(utils.filter_comments_and_blanks(workloads_list_file))

  workload_dir = env_con.fields["workload_path"]

  env_con.username_check()

  print("Binaries launching: ")
  utils.list_col_print(binaries)
  print("Launching workloads: ")
  utils.list_col_print(workloads)

  ################################################################
# Leaving this in beyond --yall to prevent accidently
# launching too many jobs
  ################################
  print(f"Launching {len(binaries) * len(workloads)} continue? [Y/N]")
  cont = input().lower()
  if cont != "y":
    print("Exiting job launch...")
    exit()
  print("Launching jobs...")
# ################################
# ##############################################################

  binaries_path = env_con.fields["binaries_path"]

  # Create results dir and capture the run number so logs can mirror it
  if env_con.output_path == "":
    results_path, run_count = create_results_directory(env_con)
  else:
    results_path = env_con.output_path
    # Infer the run number from the tail of the provided path so the log
    # directory still matches (e.g. ".../1_cores/3/" -> run_count = "3")
    run_count = os.path.basename(results_path.rstrip("/"))

  # Create the parallel logs directory under job_files/
  logs_path = create_logs_directory(env_con, run_count)

  warmup   = env_con.fields["warmup"]
  sim_inst = env_con.fields["sim_inst"]

  launch_str      = "{}{} --warmup-instructions {} --simulation-instructions {} {}\n"
  results_output_s = ""
  trace_str        = ""
  output_name      = ""
  num_launch       = 0

  print(f"Job binaries: {binaries}")

  for a in binaries:
    for b in workloads:
      splitload = b.split(" ")
      multiwl   = len(splitload) > 1
      env_con.fields["current_binary"] = a

      results_output_s = "_".join(subwl.strip() for subwl in splitload) + "_multi" if multiwl else str(b)
      trace_str        = "".join(f"{workload_dir}{subwl.strip()} " for subwl in splitload) if multiwl else f"{workload_dir}{b}"

      json_flag = ""
      if env_con.fields["enable_json_output"]:
        json_flag = " --json"

      output_name = f"{results_output_s}_{a}_"

      # Simulation output file — lives in results/
      results_str = f"{results_path}{results_output_s}_bin:{a}"

      # SLURM log files — lives in job_files/, flat filename (no sub-slashes)
      # Replace path separators so the name is a single flat filename token
      flat_name = output_name.replace("/", "_").replace(":", "_").rstrip("_")
      log_str   = f"{logs_path}{flat_name}"

      f_launch_str = launch_str.format(
        binaries_path,
        a,
        str(env_con.fields["warmup"]),
        str(env_con.fields["sim_inst"]) + json_flag,
        trace_str,
      )

      print(f"Launching command:    {f_launch_str}")
      print(f"Simulation output -> {results_str}")
      print(f"SLURM logs       -> {log_str}.o<jobid> / .e<jobid>")

      if env_con.fields["HPRC"]:
        sbatch_launch(env_con, f_launch_str, results_str, log_str, output_name)
      else:
        launch_simulations(env_con, f_launch_str, results_str, output_name)
      num_launch += 1
      print(f"Launching Sim #{num_launch}")