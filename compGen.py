# compGen.py
import sys
from classes import Resistor
from settings import resPreamble
from utils import saveFile, argumentParser
from api_client import fetch_cheapest_resistors

def main():
  args = argumentParser()
  
  # Ensure output directory exists for footprints
  import os
  if not os.path.exists(args.footFolder):
    try:
      os.makedirs(args.footFolder)
    except OSError as e:
      print(f"Error creating directory {args.footFolder}: {e}")
      sys.exit(1)

  match args.component:
    case "resistor":
      # 1. Fetch Data
      print(f"Fetching resistors (Power: {args.power})...")
      selected_products = fetch_cheapest_resistors(power_str=args.power, user_limit=args.limit)
      
      if not selected_products:
        print("No products found.")
        sys.exit(0)

      print(f"Processing {len(selected_products)} unique resistance values...")

      # 2. Initialize Symbol Library
      saveFile(resPreamble, args.sym, 'w')

      # 3. Process Each Resistor
      for product_json in selected_products:
        res = Resistor()
        res.parse(product_json)
        
        # Create Footprint (.kicad_mod)
        res.makeFootprint(args.footFolder, args)
        
        # Append to Symbol Library (.kicad_sym)
        res.makeSymbol(args.sym)

      # 4. Finalize Symbol Library
      saveFile(')', args.sym, 'a')
      print("Done.")

    case "capacitor":
      print('capacitor - not implemented yet')
      sys.exit(1)
    case "diode":
      print('diode - not implemented yet')
      sys.exit(1)
    case _:
      print("I'm sorry, Dave. I’m afraid I can’t do that.")
      sys.exit(1)

if __name__ == "__main__":
    main()