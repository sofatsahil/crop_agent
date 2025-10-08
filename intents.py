from difflib import get_close_matches

def recognize_intent(user_input, crops, locations):
    user_input = user_input.lower()
    parameters = {}
    
    # Extract crop
    for word in user_input.split():
        match = get_close_matches(word, crops, n=1, cutoff=0.7)
        if match:
            parameters["crop"] = match[0]
            break
    
    # Extract location
    for word in user_input.split():
        match = get_close_matches(word, locations, n=1, cutoff=0.7)
        if match:
            parameters["location"] = match[0]
            break

    # Intent detection
    irrigation_words = {"irrigation", "water", "irrigate"}
    fertilizer_words = {"fertilizer", "nutrient", "nitrogen", "npk"}
    weather_words = {"weather", "temperature", "forecast"}
    soil_words = {"soil", "moisture", "dirt"}

    if any(word in user_input for word in irrigation_words):
        return ("get_irrigation", parameters)
    elif any(word in user_input for word in fertilizer_words):
        return ("get_fertilizer", parameters)
    elif any(word in user_input for word in weather_words):
        return ("get_weather", parameters)
    elif any(word in user_input for word in soil_words):
        return ("get_soil_status", parameters)
    
    return ("unknown", parameters)