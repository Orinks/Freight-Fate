import ctypes
import os
from typing import Optional
from sral_wrapper import SRALEngines

class SRALEngine:

    """SRAL-based text-to-speech engine that implements the same interface as accessible_output3."""
    
    def __init__(self, speech_engine_mode="screen_reader"):
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
        
        # Voice control functions
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
        
        self.speech_engine_mode = speech_engine_mode
        self._initialize()
    
    def _initialize(self):
        """Initialize SRAL with current mode."""
        # First uninitialize if already initialized
        self.sral.SRAL_Uninitialize()
        
        # Define screen reader engines in priority order
        SCREEN_READERS = [
            ("NVDA", SRALEngines.NVDA),
            ("Narrator", SRALEngines.NARRATOR),
            ("JAWS", SRALEngines.JAWS),
            ("UIA", SRALEngines.UIA)
        ]
        
        if self.speech_engine_mode == "screen_reader":
            # Try each screen reader in order
            for name, engine in SCREEN_READERS:
                # Only include this screen reader, exclude others
                engines_exclude = ~engine
                if self.sral.SRAL_Initialize(engines_exclude):
                    print(f"Successfully initialized with {name}")
                    return
                    
            # If no screen reader available, try any available engine except SAPI
            engines_exclude = SRALEngines.SAPI
            if self.sral.SRAL_Initialize(engines_exclude):
                print("Successfully initialized with available screen reader")
                return
                
            raise RuntimeError("Failed to initialize SRAL with any screen reader")
            
        elif self.speech_engine_mode == "sapi":
            # Try SAPI only
            if not self.sral.SRAL_Initialize(~SRALEngines.SAPI):
                raise RuntimeError("Failed to initialize SRAL with SAPI")
            print("Successfully initialized with SAPI")
        else:
            # Unknown mode, try any available engine
            if not self.sral.SRAL_Initialize(0):
                raise RuntimeError("Failed to initialize SRAL")
            print("Successfully initialized with default engine")
            
        # Verify initialization succeeded
        if not self.sral.SRAL_IsInitialized():
            raise RuntimeError("SRAL initialization verification failed")
    
    def set_mode(self, mode):
        """Change the speech engine mode."""
        if mode != self.speech_engine_mode:
            self.speech_engine_mode = mode
            self._initialize()
    
    def get_available_voices(self) -> list[str]:
        """Get a list of available voice names."""
        try:
            voice_count = self.sral.SRAL_GetVoiceCount()
            voices = []
            for i in range(voice_count):
                self.sral.SRAL_GetVoiceName.restype = ctypes.c_char_p
                voice_name = self.sral.SRAL_GetVoiceName(ctypes.c_uint64(i))
                if voice_name:
                    voices.append(voice_name.decode('utf-8'))
            return voices
        except AttributeError:
            return []

    def set_voice_by_index(self, index: int) -> bool:
        """Set voice by index."""
        try:
            return self.sral.SRAL_SetVoice(ctypes.c_uint64(index))
        except AttributeError:
            return False

    def get_current_voice(self) -> int:
        """Get current voice index."""
        try:
            # Use voice count to validate current voice
            voice_count = self.sral.SRAL_GetVoiceCount()
            for i in range(voice_count):
                if self.sral.SRAL_GetVoiceName(ctypes.c_uint64(i)):
                    return i
        except AttributeError:
            pass
        return -1

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
    
    def set_voice_by_name(self, voice_name: str) -> bool:
        """Set voice by name."""
        try:
            voices = self.get_available_voices()
            if voice_name in voices:
                index = voices.index(voice_name)
                return self.set_voice_by_index(index)
        except Exception:
            pass
        return False
    
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
            voice_name: Name of the voice to use
            rate: Speech rate (0-100)
            volume: Volume level (0-100)
            pitch: Pitch level (0-100)
            
        Returns:
            bool: True if all requested parameters were set successfully
        """
        success = True
        
        if voice_name is not None:
            success &= self.set_voice_by_name(voice_name)
        
        if rate is not None:
            success &= self.set_rate(rate)
            
        if volume is not None:
            success &= self.set_volume(volume)
            
        if pitch is not None:
            try:
                PARAM_PITCH = 4  # Pitch parameter
                current_engine = self.sral.SRAL_GetCurrentEngine()
                success &= self.sral.SRAL_SetEngineParameter(current_engine, PARAM_PITCH, pitch)
            except AttributeError:
                success = False
            
        return success

    def __del__(self):
        """Clean up SRAL when the engine is destroyed."""
        if hasattr(self, 'sral'):
            self.sral.SRAL_Uninitialize()
