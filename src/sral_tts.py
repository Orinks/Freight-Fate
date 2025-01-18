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
        
<<<<<<< HEAD
        # SAPI voice functions
        self.sral.SRAL_GetSapiVoices.argtypes = []
        self.sral.SRAL_GetSapiVoices.restype = ctypes.c_char_p
        
        self.sral.SRAL_SetSapiVoice.argtypes = [ctypes.c_int]
        self.sral.SRAL_SetSapiVoice.restype = ctypes.c_bool
        
        self.sral.SRAL_GetCurrentSapiVoice.argtypes = []
        self.sral.SRAL_GetCurrentSapiVoice.restype = ctypes.c_int
=======
        self.sral.SRAL_GetVoiceCount.argtypes = []
        self.sral.SRAL_GetVoiceCount.restype = ctypes.c_uint64
        
        self.sral.SRAL_GetVoiceName.argtypes = [ctypes.c_uint64]
        self.sral.SRAL_GetVoiceName.restype = ctypes.c_char_p
        
        self.sral.SRAL_SetVoice.argtypes = [ctypes.c_uint64]
        self.sral.SRAL_SetVoice.restype = ctypes.c_bool
        
        self.sral.SRAL_SetRate.argtypes = [ctypes.c_uint64]
        self.sral.SRAL_SetRate.restype = ctypes.c_bool
        
        self.sral.SRAL_SetVolume.argtypes = [ctypes.c_uint64]
        self.sral.SRAL_SetVolume.restype = ctypes.c_bool
        
        self.sral.SRAL_SetEngineParameter.argtypes = [ctypes.c_int, ctypes.c_int, ctypes.c_int]
        self.sral.SRAL_SetEngineParameter.restype = ctypes.c_bool
>>>>>>> main
        
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
    
<<<<<<< HEAD
    def get_sapi_voices(self) -> list[str]:
        """Get list of available SAPI voices."""
        if hasattr(self.sral, 'SRAL_GetSapiVoices'):
            voices_str = self.sral.SRAL_GetSapiVoices()
            if voices_str:
                return voices_str.decode('utf-8').split('|')
        return []
    
    def set_sapi_voice(self, index: int) -> bool:
        """Set current SAPI voice by index."""
        if hasattr(self.sral, 'SRAL_SetSapiVoice'):
            return self.sral.SRAL_SetSapiVoice(index)
        return False
    
    def get_current_sapi_voice(self) -> int:
        """Get current SAPI voice index."""
        if hasattr(self.sral, 'SRAL_GetCurrentSapiVoice'):
            return self.sral.SRAL_GetCurrentSapiVoice()
        return -1
    
=======
>>>>>>> main
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
    
    def get_available_voices(self) -> list[str]:
        """Get a list of available voice names."""
        if self.speech_engine_mode != "sapi":
            return []
            
        voice_count = self.sral.SRAL_GetVoiceCount()
        voices = []
        for i in range(voice_count):
            voice_name = self.sral.SRAL_GetVoiceName(i)
            if voice_name:
                voices.append(voice_name.decode('utf-8'))
        return voices
    
    def set_voice_by_name(self, voice_name: str) -> bool:
        """Set voice by name."""
        if self.speech_engine_mode != "sapi":
            return False
            
        voices = self.get_available_voices()
        try:
            index = voices.index(voice_name)
            return self.sral.SRAL_SetVoice(index)
        except ValueError:
            return False
    
    def set_voice_by_index(self, index: int) -> bool:
        """Set voice by index."""
        if self.speech_engine_mode != "sapi":
            return False
            
        return self.sral.SRAL_SetVoice(index)
    
    def set_rate(self, rate: int) -> bool:
        """Set speech rate (0-100)."""
        if not 0 <= rate <= 100:
            return False
        return self.sral.SRAL_SetRate(rate)
    
    def set_volume(self, volume: int) -> bool:
        """Set speech volume (0-100)."""
        if not 0 <= volume <= 100:
            return False
        return self.sral.SRAL_SetVolume(volume)
    
    def set_pitch(self, pitch: int) -> bool:
        """Set speech pitch (0-100). Only works in SAPI mode."""
        if self.speech_engine_mode != "sapi":
            return False
            
        if not 0 <= pitch <= 100:
            return False
            
        PARAM_PITCH = 4  # SAPI pitch parameter
        return self.sral.SRAL_SetEngineParameter(SRALEngines.SAPI, PARAM_PITCH, pitch)

    def configure_voice(self, voice_name: Optional[str] = None, rate: Optional[int] = None, 
                       volume: Optional[int] = None, pitch: Optional[int] = None) -> bool:
        """Configure multiple voice parameters at once.
        
        Args:
            voice_name: Name of the voice to use (SAPI only)
            rate: Speech rate (0-100)
            volume: Volume level (0-100)
            pitch: Pitch level (0-100, SAPI only)
            
        Returns:
            bool: True if all requested parameters were set successfully
        """
        success = True
        
        if voice_name is not None and self.speech_engine_mode == "sapi":
            success &= self.set_voice_by_name(voice_name)
        
        if rate is not None:
            success &= self.set_rate(rate)
            
        if volume is not None:
            success &= self.set_volume(volume)
            
        if pitch is not None and self.speech_engine_mode == "sapi":
            success &= self.set_pitch(pitch)
            
        return success

    def __del__(self):
        """Clean up SRAL when the engine is destroyed."""
        if hasattr(self, 'sral'):
            self.sral.SRAL_Uninitialize()
