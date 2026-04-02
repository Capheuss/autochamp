import os
import itertools
import champc_lib.utils as utils

def parse_targets_file(build_list, config_path):
    with open(build_list) as build_file:
      for line in utils.filter_comments_and_blanks(build_file):
          target = os.path.join(config_path, line.strip())
          if os.path.exists(target):
              print("Found configuration", target)
              yield target
          else:
              print("Configuration", target, "not found ")
              exit()


def build_champsim(env_con):
    build_list = env_con.fields["build_list"]
    if build_list == "all":
        targets = itertools.chain(*((os.path.join(base,f) for f in files) for base,_,files in os.walk(env_con.fields['configs_path'])))
        targets = filter(lambda t: os.path.splitext(t)[1] == '.json', targets)
    else:
        targets = parse_targets_file(build_list, env_con.fields['configs_path'])

    for f in targets:
        print(f"Building configuration: {f}")
        os.system("{}config.sh {}".format(env_con.fields['champsim_root'], f))
        os.system("make -C "+env_con.fields['champsim_root'])