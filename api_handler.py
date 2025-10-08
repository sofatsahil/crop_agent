import requests
from datetime import datetime
from config import Config as conf

# ---------- AUTH ----------
def authenticate(username, password):
    """
    Robust token fetch: try both 'userName' and 'username' form keys.
    Prints server body if 4xx/5xx for easy diagnosis.
    """
    url = conf.TOKEN_URL
    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    forms = [
        {"userName": username, "password": password, "grant_type": "password"},
        {"username": username, "password": password, "grant_type": "password"},
    ]
    last_err = None
    for i, data in enumerate(forms, 1):
        try:
            resp = requests.post(url, headers=headers, data=data, timeout=20)
            if resp.status_code >= 400:
                # help debug: print the response text
                print(f"Auth attempt {i} failed ({resp.status_code}): {resp.text[:600]}")
            resp.raise_for_status()
            token = resp.json().get("access_token")
            if not token:
                print("❌ No access_token in response:", resp.text[:600])
                continue
            return token
        except requests.RequestException as e:
            last_err = e
    print("❌ Authentication failed:", last_err)
    return None

# ---------- COMMON LOOKUPS ----------
def _auth_headers(token):
    return {"Authorization": f"Bearer {token}"}

def list_ranches(token):
    """Return the ranch list objects from /v2/ranches.json"""
    resp = requests.get(conf.RANCHES, headers=_auth_headers(token), timeout=20)
    resp.raise_for_status()
    return resp.json()

def get_ranch_identifiers(ranch_name, token):
    """
    Find a ranch by name (case/space-insensitive).
    Return (numeric_id, external_guid_or_none).
    """
    target = (ranch_name or "").strip().lower()
    for r in list_ranches(token):
        name = (r.get("Name") or "").strip().lower()
        if name == target:
            # v2 returns Id; sometimes Ranch_External_GUID appears
            return r.get("Id"), r.get("Ranch_External_GUID")
    return None, None

def get_ranch_id(ranch_name, token):
    rid, _ = get_ranch_identifiers(ranch_name, token)
    return rid

def get_crop_type_id(crop_name, token):
    """Return crop type Id by exact case-insensitive match on Name."""
    resp = requests.get(conf.CROP_TYPES, headers=_auth_headers(token), timeout=20)
    resp.raise_for_status()
    crop_name = (crop_name or "").strip().lower()
    for c in resp.json():
        # v2 usually exposes Id + Name for crop types
        if (c.get("Name") or "").strip().lower() == crop_name:
            return c.get("Id") or c.get("CropTypeId")
    return None

def get_crops(token):
    try:
        resp = requests.get(conf.CROP_TYPES, headers=_auth_headers(token), timeout=20)
        resp.raise_for_status()
        return [(c.get("Name") or "").lower() for c in resp.json() if c.get("Name")]
    except Exception as e:
        print("❌ Could not load crops:", e)
        return []

def get_locations(token):
    try:
        ranches = list_ranches(token)
        return [(r.get("Name") or "").lower() for r in ranches if r.get("Name")]
    except Exception as e:
        print("❌ Could not load locations:", e)
        return []

# ---------- WEATHER ----------
def get_weather_update(location, token):
    """
    Try GUID first: /v2/weather/stations.json?ranchGuid=...
    Fallback numeric: /v2/weather/stations.json?ranchId=...
    """
    ranch_id, ranch_guid = get_ranch_identifiers(location, token)
    if not (ranch_guid or ranch_id):
        return "❌ Location not found"

    # try GUID
    try:
        resp = requests.get(conf.WEATHER_STATIONS, headers=_auth_headers(token),
                            params={"ranchGuid": ranch_guid} if ranch_guid else None, timeout=20)
        if resp.status_code == 200 and resp.json():
            station = resp.json()[0]
            # Example-only fields; adjust to your actual payload
            return (f"Current weather: {station.get('temp_c','?')}°C, "
                    f"{station.get('conditions','?')}, Wind: {station.get('wind_speed','?')} kph")
    except requests.RequestException:
        pass

    # fallback numeric
    try:
        resp = requests.get(conf.WEATHER_STATIONS, headers=_auth_headers(token),
                            params={"ranchId": ranch_id} if ranch_id else None, timeout=20)
        resp.raise_for_status()
        station = resp.json()[0]
        return (f"Current weather: {station.get('temp_c','?')}°C, "
                f"{station.get('conditions','?')}, Wind: {station.get('wind_speed','?')} kph")
    except requests.RequestException as e:
        return f"❌ Weather data unavailable: {str(e)}"

# ---------- PLANTINGS ----------
def get_plantings_for_ranch(token, ranch_name, active=True, commodity_type_id=None):
    """
    Prefer GUID path:  GET /v2/ranches/{Ranch_External_GUID}/plantings.json?active=true
    Fallback numeric:  GET /v2/plantings/list-by-ranch.json?ranchId={Id}&active=true
    """
    ranch_id, ranch_guid = get_ranch_identifiers(ranch_name, token)
    if not (ranch_id or ranch_guid):
        return [], f"❌ Ranch '{ranch_name}' not found"

    headers = _auth_headers(token)
    params = {}
    if active is not None:
        params["active"] = "true" if active else "false"
    if commodity_type_id:
        params["commodityTypeId"] = commodity_type_id

    # Try GUID path first
    if ranch_guid:
        url = conf.PLANTINGS_BY_RANCH_GUID.format(ranch_guid=ranch_guid)
        try:
            r = requests.get(url, headers=headers, params=params, timeout=25)
            r.raise_for_status()
            return r.json(), None
        except requests.RequestException:
            pass  # fall back

    # Numeric fallback
    url = conf.PLANTINGS_BY_RANCH_ID
    params_num = dict(params)
    params_num["ranchId"] = ranch_id
    try:
        r = requests.get(url, headers=headers, params=params_num, timeout=25)
        r.raise_for_status()
        return r.json(), None
    except requests.RequestException as e:
        return [], f"❌ Failed to fetch plantings: {e}"

def count_plantings(token, ranch_name):
    plantings, err = get_plantings_for_ranch(token, ranch_name, active=True)
    if err:
        return err
    return f"🌱 You have {len(plantings)} active plantings in {ranch_name}."

# ---------- IRRIGATION & FERTILIZER (example) ----------
def get_irrigation_recommendation(crop, location, token):
    crop_type_id = get_crop_type_id(crop, token)
    ranch_id = get_ranch_id(location, token)
    if not crop_type_id or not ranch_id:
        return "❌ Invalid crop or location"

    payload = {
        "EventDate": datetime.now().date().isoformat(),
        "CropTypeId": crop_type_id,
        "RanchId": ranch_id,
        "DistributionUniformity": 85.0
    }
    try:
        resp = requests.post(conf.IRRIGATION, json=payload,
                             headers={**_auth_headers(token), "Content-Type": "application/json"},
                             timeout=25)
        resp.raise_for_status()
        data = resp.json()
        recommended = data.get("RecommendedWater") or data.get("recommended") or 0
        return f"Recommended irrigation: {float(recommended):.2f} inches"
    except requests.RequestException as e:
        return f"❌ Irrigation recommendation failed: {str(e)}"

def get_fertilizer_recommendation(crop, location, token):
    crop_type_id = get_crop_type_id(crop, token)
    ranch_id = get_ranch_id(location, token)
    if not crop_type_id or not ranch_id:
        return "❌ Invalid crop or location"

    payload = {
        "CropTypeId": crop_type_id,
        "RanchId": ranch_id,
        "RecommendationType": "nitrogen"
    }
    try:
        resp = requests.post(conf.FERTILIZER, json=payload,
                             headers={**_auth_headers(token), "Content-Type": "application/json"},
                             timeout=25)
        resp.raise_for_status()
        data = resp.json()
        amt  = data.get("amount") or data.get("Amount") or 0
        unit = data.get("unit") or data.get("Unit") or "units"
        nutr = data.get("nutrient") or data.get("Nutrient") or "N"
        return f"Apply {amt} {unit} of {nutr}"
    except requests.RequestException as e:
        return f"❌ Fertilizer recommendation failed: {str(e)}"

# ---------- INTENT ROUTER ----------
def handle_intent(intent, parameters, auth):
    token = auth.get("token")
    crop = parameters.get("crop")
    location = parameters.get("location")

    if intent == "get_irrigation":
        if not all([crop, location]):
            return "❌ Please specify crop and location"
        return get_irrigation_recommendation(crop, location, token)

    elif intent == "get_fertilizer":
        if not all([crop, location]):
            return "❌ Please specify crop and location"
        return get_fertilizer_recommendation(crop, location, token)

    elif intent == "get_weather":
        if not location:
            return "❌ Please specify location"
        return get_weather_update(location, token)

    elif intent == "get_plantings_count":
        if not location:
            return "❌ Please specify ranch (e.g., 'How many plantings in Pryor Ranch?')"
        return count_plantings(token, location)

    return "❌ Intent not recognized"
