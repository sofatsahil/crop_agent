"""
Agricultural guidance system providing basic recommendations when APIs are unavailable.
Contains general guidelines for common crops.
"""

# Basic irrigation guidelines by crop type (inches per week during growing season)
IRRIGATION_GUIDELINES = {
    "vegetables": {
        "lettuce": "1.0-1.5 inches per week. Keep soil consistently moist but not waterlogged.",
        "spinach": "1.0-1.2 inches per week. Regular watering is essential for tender leaves.",
        "broccoli": "1.0-1.5 inches per week. Deep, infrequent watering preferred.",
        "cabbage": "1.0-1.5 inches per week. Consistent moisture prevents splitting.",
        "carrot": "0.5-1.0 inches per week. Reduce watering as roots mature.",
        "tomato": "1.0-2.0 inches per week. Deep watering at soil level preferred.",
        "pepper": "1.0-1.5 inches per week. Avoid overhead watering.",
        "onion": "0.5-1.0 inches per week. Reduce watering before harvest.",
        "default": "1.0-1.5 inches per week. Monitor soil moisture and adjust based on weather."
    },
    "fruits_nuts": {
        "strawberry": "1.0-1.5 inches per week. Drip irrigation recommended.",
        "grape": "0.5-1.0 inches per week during growing season. Reduce before harvest.",
        "almond": "3-4 feet per year total. Critical during nut development.",
        "walnut": "3-4 feet per year total. Deep watering preferred.",
        "citrus": "Deep watering 1-2 times per week. Adjust seasonally.",
        "default": "Monitor soil moisture. Deep, infrequent watering generally preferred."
    },
    "grains_forage": {
        "alfalfa": "2-3 inches per cutting cycle. Critical for yield and quality.",
        "corn": "1.0-1.5 inches per week. Critical during tasseling and filling.",
        "default": "1.0-1.5 inches per week during active growth periods."
    }
}

# Basic fertilizer guidelines
FERTILIZER_GUIDELINES = {
    "vegetables": {
        "lettuce": "Light nitrogen feeder. Apply 50-100 lbs N/acre per season.",
        "spinach": "Moderate nitrogen needs. Apply 75-125 lbs N/acre per season.",
        "broccoli": "Heavy nitrogen feeder. Apply 150-200 lbs N/acre per season.",
        "cabbage": "Heavy nitrogen feeder. Apply 150-200 lbs N/acre per season.",
        "tomato": "Apply 100-150 lbs N/acre. Reduce nitrogen before fruiting.",
        "pepper": "Moderate feeder. Apply 75-125 lbs N/acre per season.",
        "default": "Generally require balanced NPK. Nitrogen needs vary by crop type."
    },
    "fruits_nuts": {
        "strawberry": "Apply 50-75 lbs N/acre annually. Avoid excess nitrogen.",
        "grape": "Apply 20-40 lbs N/acre annually. Monitor vine vigor.",
        "almond": "Apply 150-300 lbs N/acre annually based on yield goals.",
        "walnut": "Apply 100-200 lbs N/acre annually. Timing is critical.",
        "citrus": "Apply 100-200 lbs N/acre annually in split applications.",
        "default": "Perennial crops benefit from soil testing and balanced nutrition."
    },
    "grains_forage": {
        "alfalfa": "Fix own nitrogen. Focus on phosphorus and potassium.",
        "corn": "Apply 150-250 lbs N/acre based on yield goals and soil tests.",
        "default": "Soil testing recommended for optimal fertilizer programs."
    }
}

def get_crop_category(crop_name):
    """Determine the category of a crop for guidance lookup"""
    crop_lower = crop_name.lower()
    
    vegetable_keywords = [
        'lettuce', 'spinach', 'cabbage', 'carrot', 'tomato', 'pepper', 'broccoli', 
        'cauliflower', 'celery', 'onion', 'cucumber', 'eggplant', 'pea', 'kale', 
        'cilantro', 'endive', 'escarole', 'fennel', 'mizuna', 'arugula', 'bok choy', 
        'chinese cabbage', 'napa cabbage', 'pak choi', 'brussels sprouts', 'artichoke', 
        'zucchini', 'watermelon', 'chili', 'hibiscus'
    ]
    
    fruit_nut_keywords = [
        'strawberry', 'grape', 'almond', 'walnut', 'pistachio', 'orange', 
        'lemon', 'mandarin', 'pear', 'prune', 'raspberry'
    ]
    
    grain_forage_keywords = ['alfalfa', 'corn']
    
    if any(keyword in crop_lower for keyword in vegetable_keywords):
        return "vegetables"
    elif any(keyword in crop_lower for keyword in fruit_nut_keywords):
        return "fruits_nuts"
    elif any(keyword in crop_lower for keyword in grain_forage_keywords):
        return "grains_forage"
    else:
        return "vegetables"  # Default

def get_irrigation_guidance(crop_name):
    """Get basic irrigation guidance for a crop"""
    category = get_crop_category(crop_name)
    crop_lower = crop_name.lower()
    
    guidelines = IRRIGATION_GUIDELINES[category]
    
    # Check for specific crop match
    for crop_key, guidance in guidelines.items():
        if crop_key != "default" and crop_key in crop_lower:
            return f"💧 General Irrigation Guidance: {guidance}"
    
    # Return default guidance for category
    return f"💧 General Irrigation Guidance: {guidelines['default']}"

def get_fertilizer_guidance(crop_name):
    """Get basic fertilizer guidance for a crop"""
    category = get_crop_category(crop_name)
    crop_lower = crop_name.lower()
    
    guidelines = FERTILIZER_GUIDELINES[category]
    
    # Check for specific crop match
    for crop_key, guidance in guidelines.items():
        if crop_key != "default" and crop_key in crop_lower:
            return f"🌱 General Fertilizer Guidance: {guidance}"
    
    # Return default guidance for category
    return f"🌱 General Fertilizer Guidance: {guidelines['default']}"

def get_general_notes():
    """Get general agricultural notes"""
    return """
📋 Important Notes:
• These are general guidelines - actual needs vary by soil, climate, and growing conditions
• Soil testing is recommended for precise fertilizer recommendations
• Local weather and irrigation water quality should be considered
• Consult local agricultural extension services for region-specific advice
"""