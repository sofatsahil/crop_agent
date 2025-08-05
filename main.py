import os
from dotenv import load_dotenv
from api_handler import authenticate, handle_intent, get_crops, get_locations
from intents import recognize_intent
from tts_engine import speak

load_dotenv()

def main():
    print("🌱 CropManage Voice Agent v2.0")
    print("Available commands:")
    print("- Irrigation: 'How much water for strawberries in Salinas?'")
    print("- Fertilizer: 'Nitrogen recommendation for lettuce'")
    print("- Weather: 'What's the weather in Watsonville?'")
    print("Type 'exit' to quit\n")

    # Authentication
    token = authenticate(os.getenv("CROP_USERNAME"), os.getenv("CROP_PASSWORD"))
    if not token:
        print("❌ Login failed")
        return

    auth = {"token": token}
    crops = get_crops(token)
    locations = get_locations(token)

    while True:
        try:
            user_input = input("You: ").strip()
            if user_input.lower() in {"exit", "quit", "bye"}:
                speak("Goodbye!")
                break

            intent, params = recognize_intent(user_input, crops, locations)
            
            # Show understood parameters
            if params:
                print(f"🔎 Detected: {', '.join(f'{k}:{v}' for k,v in params.items())}")
            
            # Handle missing parameters
            if intent in {"get_irrigation", "get_fertilizer"}:
                if "crop" not in params:
                    print(f"Available crops: {', '.join(crops)}")
                    params["crop"] = input("Which crop? ").lower()
                if "location" not in params:
                    print(f"Available locations: {', '.join(locations)}")
                    params["location"] = input("Which location? ").lower()

            response = handle_intent(intent, params, auth)
            print("Agent:", response)
            speak(response)

        except Exception as e:
            print(f"❌ Error: {str(e)}")
            speak("Sorry, I encountered an error")

if __name__ == "__main__":
    main()