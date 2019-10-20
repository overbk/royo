#!/usr/bin/python2.7

import os
import sys
import shutil
import re

if not os.path.exists('docker_images'):
  sys.exit("Expecting a directory named \"docker_images\" in the same directory.")

if len(sys.argv) != 2 or not sys.argv[1].endswith(".royo"):
  sys.exit("Provide exactly one argument: the .royo file.")

def path_split_all(path):
  if path == '': return ['']

  head, tail = os.path.split(path)
  return path_split_all(head) + [tail]

# PARSE ALIASES

royo = open("iterating_doubler.royo",'r')
text = royo.read()
royo.close()

# name :: type [ comma separated list of additional attributes ]
# attributes have docker-compose syntax, i.e.  attribute: value
# no support for nested attributes at the moment
type_pattern = re.compile("\s*(\S*)\s*::\s*(\S*)\s*(?:\[\s*([^]]*?)\s*\])?")

# name -> other_name [ optional condition to be inlined ]
channel_pattern = re.compile("\s*(\S*)\s*->\s*(\S*)\s*(?:\[\s*([^]]*?)\s*\])?")

alias_pattern = re.compile("\s*(\S*)\s*=\s*{([^}]*)}", re.DOTALL | re.MULTILINE)

in_pattern = re.compile("\s*in\s*(\S*)")
out_pattern = re.compile("\s*out\s*(\S*)")

matches = re.findall(alias_pattern, text)

aliases = set()
alias2components = {}
alias2channels = {}
alias2in = {}
alias2out = {}
aliasname2attributes = {}
aliaschannel2condition = {}
alias2types = {}

for name, body in matches:
  aliases.add(name)
  alias2components[name] = set()
  alias2channels[name] = set()
  alias2types[name] = set()

  for line in body.split("\n"):
    type_match = re.match(type_pattern, line)
    if type_match:
      component_name = type_match.group(1)
      component_type = type_match.group(2)
      alias2components[name].add((component_name, component_type))
      alias2types[name].add(component_type)
      aliasname2attributes[(name, component_name)] = type_match.group(3)
      continue

    channel_match = re.match(channel_pattern, line)
    if channel_match:
      component_src = channel_match.group(1)
      component_target = channel_match.group(2)
      condition = channel_match.group(3)
      alias2channels[name].add((component_src, component_target))
      aliaschannel2condition[(name, component_src, component_target)] = condition
      continue

    in_match = re.match(in_pattern, line)
    if in_match:
      alias2in[name] = in_match.group(1)
      continue

    out_match = re.match(out_pattern, line)
    if out_match:
      alias2out[name] = out_match.group(1)
      continue

# PARSE NONALIASES

types = set()
names = set()
name2type = {}
name2attributes = {}
channels = set()
channel2condition = {}

royo = open(sys.argv[1], 'r')
lines = royo.readlines()

scanning_alias = False
for line in lines:
  if "{" in line:
    scanning_alias = True
    continue
  if scanning_alias and "}" not in line:
    continue
  if scanning_alias and "}" in line:
    scanning_alias = False
    continue

  type_match = re.match(type_pattern, line)

  if type_match:
    name = type_match.group(1)
    type = type_match.group(2)
    name2type[name] = type
    types.add(type)
    name2attributes[name] = type_match.group(3)
    continue

  channel_match = re.match(channel_pattern, line)
  if channel_match:
    src = channel_match.group(1)
    target = channel_match.group(2)
    condition = channel_match.group(3)
    names.add(src)
    names.add(target)
    channel = (src, target)
    channels.add(channel)
    channel2condition[channel] = condition

# GENERATE SOURCES

shutil.rmtree('target', ignore_errors=True)

put_pattern = re.compile("(\s*)@ROYO_PUT\s+(\S*)\s*")
get_pattern = re.compile("(\s*)@ROYO_GET\s+(\S*)\s*")

expanded_types = types

while True:
  last_iteration = True
  for type in types:
    if type in aliases:
      last_iteration = False
      expanded_types = expanded_types.union(alias2types[type])
      expanded_types.remove(type)
  types = expanded_types

  if last_iteration:
    break

for file_dir, dir, files in os.walk('docker_images'):
  for file in files:
    if (file in [".DS_Store"]): # skip over any garbage files
      continue

    if (file_dir == 'docker_images'):
      sys.exit("Expecting \"docker_images\" to contain image directories only.")

    # removes docker_images/ prefix
    image = path_split_all(file_dir)[2]

    if not image in types: # source not needed for this build
      continue

    file_dir_flat = os.path.join(*path_split_all(file_dir)[2:])

    # rebuild flat directory structure
    # but flatten, since docker-compose.yaml must be on the same level
    if not os.path.exists(os.path.join('target', file_dir_flat)):
      os.makedirs(os.path.join('target', file_dir_flat))

    filepath_src = os.path.join(file_dir, file)
    filepath_target = os.path.join('target', file_dir_flat, file)

    if file == "Gemfile": # inject gem dependencies
      shutil.copy(filepath_src, filepath_target)
      gemfile = open(filepath_target, 'a')
      gemfile.write("gem \'httparty\'\n")
      gemfile.write("gem \'sinatra\'\n")
      continue

    if file.endswith(".rb"):
      injected = open(filepath_target, 'w')

      # inject requirements/setup
      injected.write("require \'httparty\'\n")
      injected.write("require \'sinatra\'\n\n")
      injected.write("set :bind, '0.0.0.0'\n")
      injected.write("set :port, ENV['SOURCE']\n")
      injected.write("set :logging, false\n")

      original = open(filepath_src, 'r')

      # hacky, not general
      gets_opened = 0
      for line in original:
        get_match = re.match(get_pattern, line)
        if get_match:
          leading_whitespace = get_match.group(1)
          input_identifier = get_match.group(2)
          gets_opened += 1
          injected.write("post '/' do\n"
          + input_identifier + " = JSON.parse(request.body.read)\n")
          continue

        put_match = re.match(put_pattern, line)
        if put_match:
          leading_whitespace = put_match.group(1)
          output_object = put_match.group(2)

          injected.write("royo_json = " + output_object + "\n")

          injected.write(
          """
          dests = ENV['DESTS'].split(',')
          conds = ENV['CONDS'].split(',').map{|s| s.gsub(/@ROYO_JSON/, "royo_json")}
          conds = conds.map{|s| if s.strip == "True" then "true" else s end}
          dests.zip(conds).each{|dest, cond|
            if eval(cond) then
              HTTParty.post("http://" + dest, body: royo_json, :headers => {'Content-Type'=>'application/json'})
            end
          }

          200
          """)
          continue

        # no changes needed
        injected.write(line)

      for _ in range(gets_opened):
        injected.write("end\n")
        continue

    if file.endswith(".sh"):
      injected = open(filepath_target, 'w')
      original = open(filepath_src, 'r')

      for line in original:
        put_match = re.match(put_pattern, line)
        if put_match: # inject   --- no support for conditions yet!
          leading_whitespace = put_match.group(1)
          output_object = put_match.group(2)
          injected.write(leading_whitespace
          + "OUTPUT=" + output_object + "\n"
          + leading_whitespace
          + "for DEST in $(echo $DESTS | tr , ' '); do\n"
          + leading_whitespace
          + "  curl -X POST -H \"Content-Type: application/json\" -d $OUTPUT"
          + " $DEST\n" + leading_whitespace + "done\n")
        else:
          injected.write(line)
      continue

    # no changes needed
    shutil.copy(filepath_src, filepath_target)

# PROCESS ALIASES


#types = set()
#names = set()
#name2type = {}
#name2attributes = {}
#channels = set()
#channel2condition = {}

old_names = names.copy()

while True:
  last_iteration = True
  for name in old_names:
    type = name2type[name]
    if type in aliases:
      last_iteration = False
      names.remove(name)
      for component_name, component_type in alias2components[type]:
        types.add(component_type)
        qualified_name = name + "." + component_name
        names.add(qualified_name)
        name2type[qualified_name] = component_type
        name2attributes[qualified_name] = aliasname2attributes[(type, component_name)]
      qualified_in = name + "." + alias2in[type]
      qualified_out = name + "." + alias2out[type]
      new_channels = set()
      for src, dest in channels:
        cond = channel2condition[(src, dest)]
        if src == name and dest == name:
          new_channels.add((qualified_out, qualified_in))
          channel2condition[(qualified_in, qualified_out)] = cond
          channel2condition[(src, dest)] = None
        elif src == name and dest != name:
          new_channels.add((qualified_out, dest))
          channel2condition[(qualified_out, dest)] = cond
          channel2condition[(src, dest)] = None
        elif src != name and dest == name:
          new_channels.add((src, qualified_in))
          channel2condition[(src, qualified_in)] = cond
          channel2condition[(src, dest)] = None
        else:
          new_channels.add((src, dest))
      channels = new_channels
      for src, dest in alias2channels[type]:
        qualified_src = name + "." + src
        qualified_dest = name + "." + dest
        channels.add((qualified_src, qualified_dest))
        channel2condition[(qualified_src, qualified_dest)] = aliaschannel2condition[(type, src, dest)]

  old_names = names.copy()
  if last_iteration:
    break

# GENERATE DOCKER_COMPOSE

yaml = open(os.path.join('target', 'docker-compose.yaml'), 'w')

yaml.write("version: \"3\"\n\nservices:\n")

ports = range(49152, 49152 + len(names))
name2port = dict(zip(names, ports))

for name in names:
  targets = map(lambda chan: chan[1], filter(lambda chan: chan[0] == name, channels))
  targeted_by = map(lambda chan: chan[0], filter(lambda chan: chan[1] == name, channels))

  yaml.write("  " + name + ":\n")
  yaml.write("    build: " + name2type[name] + "\n")
  yaml.write("    container_name: " + name + "\n")
  yaml.write("    image: " + name2type[name] + ":latest\n")

  if targets:
    yaml.write("    depends_on:\n")
    for dependency in targets:
      if dependency != name: # allow self-loops
        yaml.write("      - " + dependency + "\n")

  yaml.write("    environment:\n")
  yaml.write("      - SOURCE=" + str(name2port[name]) + "\n")

  conditions = map(lambda target: channel2condition[(name,target)], targets)
  conditions = map(lambda cond: cond if cond else "True", conditions)

  if targets:
    yaml.write("      - DESTS=" + ",".join(t + ":" + str(name2port[t]) for t in targets) + "\n")
    yaml.write("      - CONDS=" + ",".join(conditions) + "\n")
  if name2attributes[name]:
    attributes = map(lambda s: s.strip(), name2attributes[name].split(','))
    for attribute in attributes:
      yaml.write("    " + attribute +"\n")
