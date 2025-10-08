import requests
from datetime import datetime
from config import Config as conf

def authenticate(username, password):
    try:
        resp = requests.post(
            conf.TOKEN_URL,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            data={
                "username": username,
                "password": password,
                "grant_type": "password"
            }
        )
        resp.raise_for_status()
        return resp.json()["access_token"]
    except requests.RequestException as e:
        print("❌ Authentication failed:", e)
        return None
def get_ranch_id(location, token):
    resp = requests.get(conf.RANCHES, headers=headers)
    return next((r["RanchId"] for r in resp.json() if r["Name"].lower() == location.lower()), None)


def get_crop_type_id(crop, token):
    headers = {"Authorization": f"Bearer {token}"}
    resp = requests.get(conf.CROP_TYPES, headers=headers)
    return next((c["CropTypeId"] for c in resp.json() if c["Name"].lower() == crop.lower()), None)

def get_crops(token):
    headers = {"Authorization": f"Bearer {token}"}
    try:
        resp = requests.get(conf.CROP_TYPES, headers=headers)
        resp.raise_for_status()
        return [c["Name"].lower() for c in resp.json()]
    except Exception as e:
        print("❌ Could not load crops:", e)
        return []

def get_locations(token):
    headers = {"Authorization": f"Bearer {token}"}
    try:
        resp = requests.get(conf.RANCHES, headers=headers)
        resp.raise_for_status()
        return [r["Name"].lower() for r in resp.json()]
    except Exception as e:
        print("❌ Could not load locations:", e)
        return []

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
        resp = requests.post(
            conf.IRRIGATION,
            json=payload,
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
        )
        resp.raise_for_status()
        data = resp.json()
        return f"Recommended irrigation: {data['RecommendedWater']:.2f} inches"
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
        resp = requests.post(
            conf.FERTILIZER,
            json=payload,
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
        )
        resp.raise_for_status()
        data = resp.json()
        return f"Apply {data['amount']} {data['unit']} of {data['nutrient']}"
    except requests.RequestException as e:
        return f"❌ Fertilizer recommendation failed: {str(e)}"

def get_weather_update(location, token):
    ranch_id = get_ranch_id(location, token)
    if not ranch_id:
        return "❌ Location not found"
    
    try:
        resp = requests.get(
            f"{conf.WEATHER_STATIONS}?ranch={ranch_id}",
            headers={"Authorization": f"Bearer {token}"}
        )
        resp.raise_for_status()
        station = resp.json()[0]
        return (
            f"Current weather: {station['temp_c']}°C, "
            f"{station['conditions']}, Wind: {station['wind_speed']} kph"
        )
    except requests.RequestException as e:
        return f"❌ Weather data unavailable: {str(e)}"

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
    
    return "❌ Intent not recognized"