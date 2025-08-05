class Config:
    API_BASE = "https://api.cropmanage.ucanr.edu"
    TOKEN_URL = f"{API_BASE}/Token"
    
    # v2 Endpoints
    CROP_TYPES = f"{API_BASE}/v2/crop-types.json"
    RANCHES = f"{API_BASE}/v2/ranches.json"
    IRRIGATION = f"{API_BASE}/v2/irrigation-recommendation.json"
    FERTILIZER = f"{API_BASE}/v2/fertilizer-recommendation.json"
    WEATHER_STATIONS = f"{API_BASE}/v2/weather/stations.json"