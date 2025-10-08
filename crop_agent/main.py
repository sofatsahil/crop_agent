import os
from dotenv import load_dotenv
from api_handler import authenticate, handle_intent, get_crops, get_locations
from tts_engine import speak

load_dotenv()

def categorize_crops(crops):
    categories = {
        "Vegetables": [],
        "Fruits & Nuts": [],
        "Grains & Forage": []
    }
    
    vegetable_keywords = [
        'lettuce', 'spinach', 'cabbage', 'carrot', 'tomato', 'pepper', 'broccoli', 
        'cauliflower', 'celery', 'onion', 'cucumber', 'eggplant', 'pea', 'kale', 
        'cilantro', 'endive', 'escarole', 'fennel', 'mizuna', 'arugula', 'bok choy', 
        'chinese cabbage', 'napa cabbage', 'pak choi', 'brussels sprouts', 'artichoke', 
        'zucchini', 'watermelon', 'chili', 'cherry tomato', 'processing tomato', 
        'red bell pepper', 'hibiscus'
    ]
    
    fruit_nut_keywords = [
        'strawberry', 'grape', 'almond', 'walnut', 'pistachio', 'orange', 
        'lemon', 'mandarin', 'pear', 'prune', 'raspberry'
    ]
    
    grain_forage_keywords = ['alfalfa', 'corn']
    
    for crop in crops:
        if any(keyword in crop for keyword in vegetable_keywords):
            categories["Vegetables"].append(crop)
        elif any(keyword in crop for keyword in fruit_nut_keywords):
            categories["Fruits & Nuts"].append(crop)
        elif any(keyword in crop for keyword in grain_forage_keywords):
            categories["Grains & Forage"].append(crop)
        else:
            categories["Vegetables"].append(crop)
    
    for category in categories:
        categories[category].sort()
    
    return categories

def display_menu(title, options, start_num=1):
    print(f"\n{'='*50}")
    print(f"  {title}")
    print(f"{'='*50}")
    
    for i, option in enumerate(options, start_num):
        print(f"{i:2}. {option}")
    
    print(f"{len(options) + start_num:2}. Back to main menu")
    if start_num == 1:
        print(f"{len(options) + start_num + 1:2}. Exit")
    
    while True:
        try:
            choice = input(f"\nEnter your choice (1-{len(options) + start_num + (1 if start_num == 1 else 0)}): ").strip()
            choice_num = int(choice)
            
            if start_num <= choice_num <= len(options) + start_num - 1:
                return choice_num - start_num
            elif choice_num == len(options) + start_num:
                return "back"
            elif choice_num == len(options) + start_num + 1 and start_num == 1:
                return "exit"
            else:
                print("❌ Invalid choice. Please try again.")
        except ValueError:
            print("❌ Please enter a valid number.")

def get_recommendation_type():
    recommendations = [
        "💧 Irrigation Recommendation",
        "🌱 Fertilizer Recommendation", 
        "🌤️  Weather Information"
    ]
    
    choice = display_menu("What type of recommendation do you need?", recommendations)
    
    if choice == "exit":
        return "exit"
    elif choice == "back":
        return None
    elif choice == 0:
        return "get_irrigation"
    elif choice == 1:
        return "get_fertilizer"
    elif choice == 2:
        return "get_weather"

def get_crop_selection(crop_categories):
    categories = list(crop_categories.keys())
    category_choice = display_menu("Select crop category:", categories)
    
    if category_choice in ["exit", "back"]:
        return category_choice
    
    selected_category = categories[category_choice]
    crops_in_category = crop_categories[selected_category]
    
    crop_choice = display_menu(f"Select crop from {selected_category}:", crops_in_category)
    
    if crop_choice in ["exit", "back"]:
        return crop_choice
    
    return crops_in_category[crop_choice]

def get_location_selection(locations):
    formatted_locations = [loc.title() for loc in locations]
    location_choice = display_menu("Select location:", formatted_locations)
    
    if location_choice in ["exit", "back"]:
        return location_choice
    
    return locations[location_choice]

def main():
    print("🌱 CropManage Agricultural Assistant v3.0")
    print("📋 Menu-Driven Interface for Easy Navigation")
    print("\nAuthenticating...")

    token = authenticate(os.getenv("CROP_USERNAME"), os.getenv("CROP_PASSWORD"))
    if not token:
        print("❌ Login failed")
        return

    print("✅ Authentication successful!")
    
    print("📊 Loading crop and location data...")
    crops = get_crops(token)
    locations = get_locations(token)
    crop_categories = categorize_crops(crops)
    
    auth = {"token": token}
    
    print(f"✅ Loaded {len(crops)} crops and {len(locations)} locations")

    while True:
        try:
            recommendation_type = get_recommendation_type()
            
            if recommendation_type == "exit":
                speak("Goodbye!")
                print("\n👋 Thank you for using CropManage Agricultural Assistant!")
                break
            elif not recommendation_type:
                continue
            
            params = {}
            
            if recommendation_type in ["get_irrigation", "get_fertilizer"]:
                crop = get_crop_selection(crop_categories)
                if crop == "exit":
                    speak("Goodbye!")
                    print("\n👋 Thank you for using CropManage Agricultural Assistant!")
                    break
                elif crop == "back":
                    continue
                params["crop"] = crop.lower()
            
            location = get_location_selection(locations)
            if location == "exit":
                speak("Goodbye!")
                print("\n👋 Thank you for using CropManage Agricultural Assistant!")
                break
            elif location == "back":
                continue
            params["location"] = location.lower()
            
            print("\n🔄 Processing your request...")
            response = handle_intent(recommendation_type, params, auth)
            
            print("\n" + "="*60)
            print("📋 RECOMMENDATION RESULT")
            print("="*60)
            if recommendation_type == "get_irrigation":
                print(f"🌱 Crop: {params['crop'].title()}")
                print(f"📍 Location: {params['location'].title()}")
                print(f"💧 {response}")
            elif recommendation_type == "get_fertilizer":
                print(f"🌱 Crop: {params['crop'].title()}")
                print(f"📍 Location: {params['location'].title()}")
                print(f"🌱 {response}")
            elif recommendation_type == "get_weather":
                print(f"📍 Location: {params['location'].title()}")
                print(f"🌤️  {response}")
            print("="*60)
            
            speak(response)
            
            print("\nPress Enter to continue or type 'exit' to quit...")
            continue_choice = input().strip().lower()
            if continue_choice in ["exit", "quit", "bye"]:
                speak("Goodbye!")
                print("\n👋 Thank you for using CropManage Agricultural Assistant!")
                break

        except KeyboardInterrupt:
            speak("Goodbye!")
            print("\n\n👋 Thank you for using CropManage Agricultural Assistant!")
            break
        except Exception as e:
            print(f"❌ Error: {str(e)}")
            speak("Sorry, I encountered an error")
            print("Let's try again...")

if __name__ == "__main__":
    main()