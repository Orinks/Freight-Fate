import ctypes
import os
from typing import Optional

class SRALEngine:
    """SRAL-based text-to-speech engine that implements the same interface as accessible_output3."""
    
    def __init__(self):
        """Initialize SRAL text-to-speech engine."""
        # Load SRAL DLL
        dll_path = os.path.join(os.path.dirname(__file__), "SRAL.dll")
        self.sral = ctypes.CDLL(dll_path)
        
        # Define function signatures
        self.sral.SRAL_Initialize.argtypes = [ctypes.c_int]
        self.sral.SRAL_Initialize.restype = ctypes.c_bool
        
        self.sral.SRAL_Speak.argtypes = [ctypes.c_char_p, ctypes.c_bool]
        self.sral.SRAL_Speak.restype = ctypes.c_bool
        
        self.sral.SRAL_StopSpeech.argtypes = []
        self.sral.SRAL_StopSpeech.restype = ctypes.c_bool
        
        # Initialize SRAL
        if not self.sral.SRAL_Initialize(0):  # 0 means don't exclude any engines
            raise RuntimeError("Failed to initialize SRAL")
    
    def output(self, text: str, interrupt: bool = True) -> bool:
        """Output text through speech. This matches accessible_output3's interface."""
        if not text:
            return False
        return self.sral.SRAL_Speak(text.encode('utf-8'), interrupt)
    
    def speak(self, text: str, interrupt: bool = True) -> bool:
        """Alias for output to maintain compatibility."""
        return self.output(text, interrupt)
    
    def stop(self) -> bool:
        """Stop current speech."""
        return self.sral.SRAL_StopSpeech()
    
    def __del__(self):
        """Clean up SRAL when the engine is destroyed."""
        if hasattr(self, 'sral'):
            self.sral.SRAL_Uninitialize()
