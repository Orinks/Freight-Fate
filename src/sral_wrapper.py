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
        
        # Add rate control function signatures
        self.sral.SRAL_SetRate.argtypes = [ctypes.c_uint64]
        self.sral.SRAL_SetRate.restype = ctypes.c_bool
        
        self.sral.SRAL_GetRate.argtypes = []
        self.sral.SRAL_GetRate.restype = ctypes.c_uint64
        
        # Initialize SRAL
        if not self.initialize():
            raise RuntimeError("Failed to initialize SRAL")
    
    def initialize(self, engines_exclude: int = 0) -> bool:
        """Initialize SRAL with optional engine exclusions."""
        return self.sral.SRAL_Initialize(engines_exclude)
    
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
    
    def set_rate(self, rate: int) -> bool:
        """Set the speech rate (0-100)."""
        return self.sral.SRAL_SetRate(ctypes.c_uint64(rate))

    def get_rate(self) -> int:
        """Get the current speech rate."""
        return self.sral.SRAL_GetRate()
    
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
