# utils.py
import argparse
import math
import os
from jinja2 import Environment, FileSystemLoader

# Initialize Jinja2 environment loading from current directory
env = Environment(loader=FileSystemLoader('.'))

def argumentParser():
  cmdArg = argparse.ArgumentParser(description='Generate Kicad Symbols and Footprints from Digikey API.')

  # API specific arguments
  cmdArg.add_argument("--power", help="Power rating filter (e.g., 0.25W, 1/4W)", default="0.25W")
  cmdArg.add_argument("--limit", help="API fetch limit per batch", type=int, default=50)
  cmdArg.add_argument("--voltage", help="Voltage rating filter (e.g., 5v, 6.3v, 10v)", default = "6.3v")
  # Output arguments
  cmdArg.add_argument("--footFolder", default='.', help="Folder for generated footprints")
  cmdArg.add_argument("--sym", default="symbolLibrary.kicad_sym", help="Filename of the symbols library")
  
  # Component type
  cmdArg.add_argument("--component", required=True, help="Type of component: resistor, capTHRad, diode")
  cmdArg.add_argument()
  return cmdArg.parse_args()

def grid_round_up(a):
  """
  Round the value to the next tenth of an inch (2.54mm).
  """
  return math.ceil(a/2.54)*2.54

def render_template(pathToTemplate, data):
  """
  Fills in the template and render with Jinja2
  """
  try:
    template = env.get_template(pathToTemplate)
    return template.render(data)
  except Exception as e:
    print(f"Error rendering template {pathToTemplate}: {e}")
    return ""

def checkForFootprint(fileName, pathToFootprint):
  """
  Checks if footprint already exist.
  """
  full_path = os.path.join(pathToFootprint, fileName)
  if os.path.exists(full_path):
    # print(f"The footprint exists: {fileName}")
    return True
  return False

def saveFile(content, path, mode='w'):
  """
  Saves file.
  """
  try:
    with open(path, mode, encoding="utf-8") as file:
      file.write(content)
      return True
  except IOError as e:
    print(f"Could not open {path} for writing as '{mode}'. Error: {e}")
    return False