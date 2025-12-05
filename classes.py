# classes.py
import re
import jmespath
from pathlib import Path
from settings import om, padSize
from utils import saveFile, render_template, checkForFootprint, grid_round_up

class Component:
  """Base Component Class"""
  def __init__(self):
    self.mpn = "Unknown"
    self.digikeyPN = "N/A"
    self.datasheet = ""
    self.price = 0.0
    self.dimensions_raw = "Unknown"

  def parse(self, product_json):
    """Base parser using JMESPath for common fields"""
    _MPN = jmespath.compile("ManufacturerProductNumber")
    _DKPART = jmespath.compile("""
        ProductVariations[?PackageType.Id == `2`].DigiKeyProductNumber[0]
        || ProductVariations[?PackageType.Id == `1`].DigiKeyProductNumber[0]
        || ProductVariations[0].DigiKeyProductNumber
        || 'N/A'
    """)
    _DATASHEET = jmespath.compile("DatasheetUrl")
    _PRICE = jmespath.compile("UnitPrice")
    _SIZE = jmespath.compile("Parameters[?ParameterId == `46`].ValueText | [0]")

    self.mpn = _MPN.search(product_json) or "Unknown"
    self.digikeyPN = _DKPART.search(product_json) or "N/A"
    self.datasheet = _DATASHEET.search(product_json) or ""
    self.price = _PRICE.search(product_json) or 999.99
    self.dimensions_raw = _SIZE.search(product_json) or "Unknown"

class Resistor(Component):
  """Resistor Component"""
  def __init__(self):
    super().__init__()
    self.resistance = "Unknown"
    self.tolerance = "Unknown"
    self.power = "Unknown"
    self.diameter = 0.0
    self.length = 0.0
    self.pinPitch = 0.0
    self.symbol_name = ""
    self.footprint_name = ""

  def parse(self, product_json):
    super().parse(product_json)
    
    # JMESPath specifically for Resistors
    _R = jmespath.compile("Parameters[?ParameterId == `2085`].ValueId | [0]")
    _TOL = jmespath.compile("Parameters[?ParameterId == `3`].ValueText | [0]")
    _PWR = jmespath.compile("Parameters[?ParameterId == `2`].ValueText | [0]")

    self.resistance = _R.search(product_json) or "Unknown"
    self.tolerance = _TOL.search(product_json) or "Unknown"
    self.power = _PWR.search(product_json) or "Unknown"

    # Post-Processing
    self.resistance = self.resistance.replace("Ohms", om)
    self.symbol_name = 'R_' + self.resistance

    # Parse Dimensions (Expects: 1.80mm x 3.30mm or similar in raw string)
    match = re.search(r'([0-9]+\.[0-9]+)mm\sx\s([0-9]+\.[0-9]+)mm', self.dimensions_raw)
    if match:
      self.diameter = round(float(match.group(1)), 3)
      self.length = round(float(match.group(2)), 3)
      self.pinPitch = grid_round_up(float(self.length))
    else:
      print(f'Dimensions malformed for {self.digikeyPN}: {self.dimensions_raw}')
      self.dimensions_raw = 'FUBAR'

  def makeFootprint(self, output_folder, args):
    if self.dimensions_raw == 'FUBAR':
      return

    self.footprint_name = f"R_Axial_L{self.length}mm_D{self.diameter}mm_P{self.pinPitch}mm_Horizontal.kicad_mod"
    
    # Check existence
    if checkForFootprint(self.footprint_name, output_folder):
      return

    # Prepare Data for Template
    footprintData = {
      'padSize': float(padSize),
      'length': float(self.length),
      'diameter': self.diameter,
      'pinPitch': self.pinPitch,
      'powerRating': self.power,
      'refOffsetX': 2.5,
      'refOffsetY': -((float(self.diameter) / 2) + 1.0),
      'valueOffsetX': 0.5,
      'valueOffsetY': (float(self.diameter) / 2) + 0.5
  }

    # Render
    # Assumes template is in templates/footprints/
    output = render_template('templates/footprints/TH_ResistorTemplate.kicad_mod', footprintData)
    
    full_path = Path(output_folder) / self.footprint_name
    saveFile(output, full_path, 'w')
    print(f"Created Footprint -> {self.footprint_name}")

  def makeSymbol(self, library_path):
    if self.resistance == "Unknown":
      return

    # Prepare path string for KiCad symbol property
    # Assumes the footprint library nickname is "DigikeyResistors"
    pseudoPathToFootprint = f'DigikeyResistors:{self.footprint_name.replace(".kicad_mod", "")}'

    symbolData = {
      'symbol': self.symbol_name,
      'value': self.resistance,
      'tolerance': self.tolerance,
      'power': self.power,
      'footprint': pseudoPathToFootprint,
      'datasheet': self.datasheet,
      'dkPart': self.digikeyPN,
      'mfrPart': self.mpn,
      'price': self.price,
    }

    # Assumes template is in templates/symbols/
    output = render_template('templates/symbols/ResistorSymbolTemplate.txt', symbolData)
    saveFile(output, library_path, 'a')

class Capacitor(Component):
  """Capacitor Component"""
  def __init__(self):
    super().__init__()
    self.capacitance = "Unknown"
    self.tolerance = "Unknown"
    self.voltage = "Unknown" 
    self.symbol_name = ""
    self.footprint_name = ""
    # Generic physical fields that may or may not be used
    self.diameter = 0.0    # used by radial, canned electrolytics, etc.
    self.height = 0.0      # used by radial electrolytics
    self.length = 0.0      # used by axial electrolytics
    self.pin_pitch = 0.0   # lead spacing (radial) or calculated (axial)
  
  def parse(self, product_json):
    super().parse(product_json)

    # JMESPath specifically for capacitors
    _C = jmespath.compile("Parameters[?ParameterId == `2049`].ValueId | [0]")
    _TOL = jmespath.compile("Parameters[?ParameterId == `3`].ValueText | [0]")
    _VOLT = jmespath.compile("Parameters[?ParameterId == `2079`].ValueText | [0]")

    self.capacitance = _C.search(product_json) or "Unknown"
    self.tolerance = _TOL.search(product_json) or "Unknown"
    self.voltage = _VOLT.search(product_json) or "Unknown"

    # Post-Processing
    self.symbol_name = 'CP_' + self.capacitance

class AluminumElectrolytic(Capacitor):
  """Aluminum Electrolytic Capacitor Component"""
  def __init__(self):
    super().__init__()
    # add attributes late if needed
    pass

class Radial(AluminumElectrolytic):
  """Radial Topology Aluminum Electrolytic Capacitor"""
  def __init__(self):
    super().__init__()

  def parse(self, product_json):
    
    super().parse(product_json)
    # JMESPath specifically for radial electrolytic capacitors
    
    _DIA_RAW = jmespath.compile("Parameters[?ParameterId == `46`].ValueText | [0]")
    _PIN_PITCH_RAW = jmespath.compile("Parameters[?ParameterId == `508`].ValueText | [0]")
    
    self.pin_pitch = _PIN_PITCH_RAW.search(product_json) or "Unknown"
    self.diameter = _DIA_RAW.search(product_json) or "Unknown"

    # Post-Processing
    self.pin_pitch = re.search(r'\(.*?\b([\d.]+)\s*mm?\b', self.pin_pitch)
    self.diameter = re.search(r'\(.*?\b([\d.]+)\s*mm?\b', self.diameter)



