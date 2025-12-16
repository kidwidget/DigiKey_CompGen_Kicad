# api_client.py
import requests
import os
import math
import pandas as pd
import re
from settings import API_LIMIT

# Digikey Credentials
client_id = os.getenv("DIGIKEY_CLIENT_ID")
client_secret = os.getenv("DIGIKEY_CLIENT_SECRET")

# Digikey API Targets
targetKeywordSearch = "https://api.digikey.com/products/v4/search/keyword"

def getToken():
  target = "https://api.digikey.com/v1/oauth2/token"
  headers = {"content-type": "application/x-www-form-urlencoded"}
  payload = {
    "client_id": client_id,
    "client_secret": client_secret,
    "grant_type": "client_credentials"
  }

  response = requests.post(target, data=payload, headers=headers)
  if response.status_code == 200:
    return response.json()['access_token']
  else:
    raise RuntimeError(f"Token request failed: {response.text}")

def _getThroughholeResistorBatch(token, power_id, limit, offset):
  """Internal helper to get a single batch"""
  
  payload = {
    "Keywords": "resistor",
    "Limit": f"{limit}",
    "Offset": f"{offset}",
    "MinimumQuantityAvailable": 1,
    "FilterOptionsRequest": {
      "CategoryFilter": [{"id": "2"}],
      "MarketPlaceFilter": "ExcludeMarketPlace",
      "ParameterFilterRequest": {
        "CategoryFilter": {"id": "53"},
        "ParameterFilters": [
          {"ParameterId": 3, "FilterValues": [{"Id": "2503"}]}, # 5% Tolerance
          {"ParameterId": 2, "FilterValues": [{"Id": f"{power_id}"}]} # Power
          ]
      },
      "SearchOptions": ["NormallyStocking"]
    },
    "ExcludedContent": ["FilterOptions"],
    "SortOptions": {"Field": "Price", "SortOrder": "Ascending"}
  }
  headers = {
    "x-digikey-client-id": client_id,
    "content-type": "application/json",
    "authorization": f"Bearer {token}"
  }
  
  response = requests.post(targetKeywordSearch, json=payload, headers=headers)
  
  # Handle token refresh if 401
  if response.status_code == 401:
    new_token = getToken()
    headers["authorization"] = f"Bearer {new_token}"
    response = requests.post(targetKeywordSearch, json=payload, headers=headers)
    return response, new_token
    
  if response.status_code != 200:
    raise RuntimeError(f"API request failed {response.status_code}: {response.text}")

  return response, token

def parseResistance(resValue: str) -> float:
  """Helper for dataframe to sort resistance"""
  value = str(resValue).strip().lower()
  match = re.match(r'^(\d+\.?\d*)\s*([kmM]?)ohms?$', value)
  if not match:
    return 0.0
  numStr, unit = match.groups()
  ohms = float(numStr)
  if unit == 'k':
    return ohms * 1000
  elif unit in ['m', 'M']:
    return ohms * 1000000
  return ohms

def extractResistanceForDF(params):
  try:
    # Parameter ID 2085 is usually Resistance
    resText = next((p['ValueText'] for p in params if p['ParameterId'] == 2085), "0 Ohms")
    return parseResistance(resText)
  except Exception:
    return 0.0

def fetch_cheapest_resistors(power_str="0.25W", user_limit=50):
  """
  Main public function to get processed resistor list.
  1. Auth
  2. Maps power string to Digikey ID (This map might need expanding)
  3. Fetches all pages
  4. Pandas processing to find cheapest
  """
  
  # Map common power strings to Digikey Parameter IDs
  # May need to add more mappings here
  power_map = {
    "0.125W": 10879,
    "1/8W": 10879,
    "0.25W": 16543,
    "1/4W": 16543
  }
  
  power_id = power_map.get(power_str, 16543) # Default to 1/4W if unknown
  
  token = getToken()
  data = []
  index = 0
  
  print(f"Getting batch number 1 for Power ID {power_id}")
  response, token = _getThroughholeResistorBatch(token, power_id, user_limit, 0)
  responseData = response.json()
  data.append(responseData)
  
  totalCount = responseData.get("ProductsCount", 0)
  print(f"Found {totalCount} resistors")

  # Pagination logic
  if totalCount > user_limit:
    numOfBatches = math.ceil(totalCount / user_limit)
    remaining = totalCount - user_limit
    index = 1
    while remaining > 0:
      print(f"Getting batch number {index + 1} of {numOfBatches}")
      response, token = _getThroughholeResistorBatch(token, power_id, user_limit, (index * user_limit))
      responseData = response.json()
      data.append(responseData)
      index += 1
      remaining -= user_limit

  # Flatten products
  all_products = []
  for batch in data:
    if "Products" in batch:
      all_products.extend(batch["Products"])

  if not all_products:
    return []

  # Pandas Processing
  df = pd.json_normalize(all_products)
  df['ResistanceOhms'] = df['Parameters'].apply(extractResistanceForDF)
  df['ResistanceGroup'] = df['ResistanceOhms'].round(3)
  
  # Find cheapest per group
  cheapest_indices = df.groupby('ResistanceGroup')['UnitPrice'].idxmin()
  
  selected_products = [all_products[i] for i in cheapest_indices]
  return selected_products

def _getThroughholeCapacitorBatch(token, voltage_id, limit, offset):
  """Internal helper to get a single batch"""
  
  payload = {
    "Keywords": "capacitor",
    "Limit": f"{limit}",
    "Offset": f"{offset}",
    "MinimumQuantityAvailable": 1,
    "FilterOptionsRequest": {
      "CategoryFilter": [{"id": "3"}], # capacitor
      "MarketPlaceFilter": "ExcludeMarketPlace",
      "ParameterFilterRequest": {
        "CategoryFilter": {"id": "58"}, # aluminum electrolytic
        "ParameterFilters":[
          {"ParameterId": 3, "FilterValues": [{ "Id": "1900" }]}, # tolerance
          {"ParameterId": 2079, "FilterValues": [{ "Id": "6.3 V" }]}, # voltage
          {"ParameterId": 52, "FilterValues": [{ "Id": "388275" }]}, # polarization
          {"ParameterId": 69, "FilterValues": [{ "Id": "411897" }]}, # throughhole
          {"ParameterId": 16, "FilterValues": [{ "Id": "392320" }]} # radial can
        ]
      },
      "SearchOptions": ["NormallyStocking"]
    },
    "ExcludedContent": ["FilterOptions"],
    "SortOptions": {"Field": "Price","SortOrder": "Ascending"}
  }
  headers = {
    "x-digikey-client-id": client_id,
    "content-type": "application/json",
    "authorization": f"Bearer {token}"
  }

  response = requests.post(targetKeywordSearch, json=payload, headers=headers)

  # Handle token refresh if 401
  if response.status_code == 401:
    new_token = getToken()
    headers["authorization"] = f"Bearer {new_token}"
    response = requests.post(targetKeywordSearch, json=payload, headers=headers)
    return response, new_token
    
  if response.status_code != 200:
    raise RuntimeError(f"API request failed {response.status_code}: {response.text}")

  return response, token

def parseCapacitance(capValue: str) -> float:
  """Helper for dataframe to sort capacitance"""
  value = str(capValue).strip().lower()
  match = re.match(r'^(\d+\.?\d*)\s*([µum]f|mf|f)$', value)
  if not match:
    return 0.0
  numStr, unit = match.groups()
  capacitance = float(numStr)
  if unit in ['pf']:
    return capacitance * 1e-12
  elif unit in ['nf']:
    return capacitance * 1e-9
  elif unit in ['µf', 'uf', 'muf']:      # µF or uF
    return capacitance * 1e-6         # 1 µF = 10⁻⁶ F
  elif unit == 'mf':                    # mF
    return capacitance * 1e-3         # 1 mF = 10⁻³ F
  elif unit == 'f':                     # F
    return capacitance                # already in Farads
  else:
    return 0.0

def extractCapacitanceForDF(params):
  try:
    # Parameter ID 2049 is Capacitance
    capText = next((p['ValueText'] for p in params if p['ParameterID'] == 2049), " 0 F")
    return parseCapacitance(capText)
  except Exception:
    return 0.0

def fetch_cheapest_capacitors(volt_str = "6.3 V", user_limit = 50):
  """
  Main public function to get processed capacitor list.
  1. Auth
  2. Not needed for Capacitors maps power string to Digikey ID (This map might need expanding)
  3. Fetches all pages
  4. Pandas processing to find cheapest
  """
  
  token = getToken()
  data = []
  index  = 0

  print(f"Getting batchg number 1 for Voltage {volt_str}")
  response, token = _getThroughholeCapacitorBatch(token, volt_str, user_limit, 0)
  responseData = response.json()
  data.append(responseData)

  totalCount = responseData.get("ProductCount", 0)
  print(f"Found {totalCount} capacitors")

 # Pagination logic
  if totalCount > user_limit:
    numOfBatches = math.ceil(totalCount / user_limit)
    remaining = totalCount - user_limit
    index = 1
    while remaining > 0:
      print(f"Getting batch number {index + 1} of {numOfBatches}")
      response, token = _getThroughholeCapacitorBatch(token, volt_str, user_limit, (index * user_limit))
      responseData = response.json()
      data.append(responseData)
      index += 1
      remaining -= user_limit
  # Flatten products
  all_products = []
  for batch in data:
    if "Products" in batch:
      all_products.extend(batch["Products"])

  if not all_products:
    return []
  # Pandas Processing
  df = pd.json_normalize(all_products)
  df['CapacitorOhms'] = df['Parameters'].apply(extractCapacitanceForDF)
  df['CapacitorGroup'] = df['CapacitorOhms'].round(3)
  
  # Find cheapest per group
  cheapest_indices = df.groupby('CapacitorGroup')['UnitPrice'].idxmin()
  
  selected_products = [all_products[i] for i in cheapest_indices]
  return selected_products


  














  
