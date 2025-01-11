import ctypes
import os
from typing import Optional

class SRALEngines:
    NONE = 0
    NVDA = 2
    SAPI = 4
    JAWS = 8
    SPEECH_DISPATCHER = 16
    UIA = 32
    AV_SPEECH = 64
    NARRATOR = 128

class SRALWrapper:
    def __init__(self):
        # Load the DLL
        dll_path = os.path.join(os.path.dirname(__file__), "SRAL.dll")
        self.sral = ctypes.CDLL(dll_path)
        
        # Define function signatures
        self.sral.SRAL_Initialize.argtypes = [ctypes.c_int]
        self.sral.SRAL_Initialize.restype = ctypes.c_bool
        
        self.sral.SRAL_Speak.argtypes = [ctypes.c_char_p, ctypes.c_bool]
        self.sral.SRAL_Speak.restype = ctypes.c_bool
        
        self.sral.SRAL_StopSpeech.argtypes = []
        self.sral.SRAL_StopSpeech.restype = ctypes.c_bool
        
        self.sral.SRAL_PauseSpeech.argtypes = []
        self.sral.SRAL_PauseSpeech.restype = ctypes.c_bool
        
        self.sral.SRAL_ResumeSpeech.argtypes = []
        self.sral.SRAL_ResumeSpeech.restype = ctypes.c_bool
        
        self.sral.SRAL_GetCurrentEngine.argtypes = []
        self.sral.SRAL_GetCurrentEngine.restype = ctypes.c_int

        # Add new function signatures for SAPI voices
        self.sral.SRAL_GetSapiVoices.argtypes = []
        self.sral.SRAL_GetSapiVoices.restype = ctypes.c_char_p
        
        self.sral.SRAL_SetSapiVoice.argtypes = [ctypes.c_int]
        self.sral.SRAL_SetSapiVoice.restype = ctypes.c_bool
        
        self.sral.SRAL_GetCurrentSapiVoice.argtypes = []
        self.sral.SRAL_GetCurrentSapiVoice.restype = ctypes.c_int
        
        # JAWS key hook
        self.sral.SRAL_InstallJawsKeyHook.argtypes = []
        self.sral.SRAL_InstallJawsKeyHook.restype = ctypes.c_bool
        
        # Initialize SRAL
        if not self.initialize():
            raise RuntimeError("Failed to initialize SRAL")
    
    def initialize(self, engines_exclude: int = 0) -> bool:
        """Initialize SRAL with optional engine exclusions."""
        success = self.sral.SRAL_Initialize(engines_exclude)
        if success and self.get_current_engine() == SRALEngines.JAWS:
            self.sral.SRAL_InstallJawsKeyHook()
        return success
    
    def speak(self, text: str, interrupt: bool = True) -> bool:
        """Speak the given text."""
        return self.sral.SRAL_Speak(text.encode('utf-8'), interrupt)
    
    def stop(self) -> bool:
        """Stop current speech."""
        return self.sral.SRAL_StopSpeech()
    
    def pause(self) -> bool:
        """Pause current speech."""
        return self.sral.SRAL_PauseSpeech()
    
    def resume(self) -> bool:
        """Resume paused speech."""
        return self.sral.SRAL_ResumeSpeech()
    
    def get_current_engine(self) -> int:
        """Get the current speech engine identifier."""
        return self.sral.SRAL_GetCurrentEngine()
    
    def get_sapi_voices(self) -> list[str]:
        """Get list of available SAPI voices."""
        if self.get_current_engine() != SRALEngines.SAPI:
            return []
        voices_str = self.sral.SRAL_GetSapiVoices()
        if not voices_str:
            return []
        return voices_str.decode('utf-8').split('|')
    
    def set_sapi_voice(self, index: int) -> bool:
        """Set current SAPI voice by index."""
        if self.get_current_engine() != SRALEngines.SAPI:
            return False
        return self.sral.SRAL_SetSapiVoice(index)
    
    def get_current_sapi_voice(self) -> int:
        """Get current SAPI voice index."""
        if self.get_current_engine() != SRALEngines.SAPI:
            return -1
        return self.sral.SRAL_GetCurrentSapiVoice()

    def __del__(self):
        """Clean up SRAL when the wrapper is destroyed."""
        if hasattr(self, 'sral'):
            self.sral.SRAL_Uninitialize()

# Example usage:
if __name__ == "__main__":
    try:
        sral = SRALWrapper()
        print(f"Current engine: {sral.get_current_engine()}")
        sral.speak("Hello, this is a test of the SRAL speech system.")
    except Exception as e:
        print(f"Error: {e}")
