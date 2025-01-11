import ctypes
import os
from typing import Optional
from sral_wrapper import SRALEngines

class SRALEngine:
    """SRAL-based text-to-speech engine that implements the same interface as accessible_output3."""
    
    def __init__(self, speech_engine_mode="default"):
        """Initialize SRAL text-to-speech engine with specified speech engine mode."""
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
        
        self.sral.SRAL_Uninitialize.argtypes = []
        self.sral.SRAL_Uninitialize.restype = None
        
        self.speech_engine_mode = speech_engine_mode
        self._initialize()
    
    def _initialize(self):
        """Initialize SRAL with current mode."""
        # First uninitialize if already initialized
        self.sral.SRAL_Uninitialize()
        
        # Initialize with appropriate mode
        engines_exclude = ~SRALEngines.SAPI if self.speech_engine_mode == "sapi" else 0
        if not self.sral.SRAL_Initialize(engines_exclude):
            raise RuntimeError("Failed to initialize SRAL")
    
    def set_mode(self, mode):
        """Change the speech engine mode."""
        if mode != self.speech_engine_mode:
            self.speech_engine_mode = mode
            self._initialize()
    
    def output(self, text: str, interrupt: bool = True) -> bool:
        """Output text through speech."""
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
