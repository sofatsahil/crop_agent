import os
import subprocess

def speak(text):
    """
    Text-to-speech function with robust error handling.
    Completely silent in environments without audio support.
    """
    # Check if we're in a cloud environment or audio is unavailable
    if not _audio_available():
        # Silent mode - TTS not available
        return
    
    try:
        import pyttsx3
        engine = pyttsx3.init()
        if engine:
            engine.say(text)
            engine.runAndWait()
            engine.stop()
            del engine
    except:
        # Any TTS error - continue silently
        pass

def _audio_available():
    """Check if audio output is available on the system"""
    try:
        # Check if aplay (ALSA) is available
        result = subprocess.run(['which', 'aplay'], 
                              capture_output=True, 
                              text=True, 
                              timeout=2)
        return result.returncode == 0
    except:
        return False