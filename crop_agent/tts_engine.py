def speak(text):
    import pyttsx3

    engine = pyttsx3.init()
    engine.say(text)
    engine.runAndWait()