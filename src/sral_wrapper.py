import ctypes
import os
import sys
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

def _resolve_sral_library_path() -> str:
    """Resolve the path to the SRAL shared library without requiring it in repo.
    Search order (per-OS):
    1) Explicit path via SRAL_DLL_PATH env var
    2) Root dir via SRAL_ROOT env var (search common subfolders)
    3) Local 'sral' or 'SRAL' directory at project root (search common subfolders)
    4) Fallback to current src/SRAL.dll for backward compatibility
    """
    system = sys.platform
    # Map platform to expected library base name
    if system.startswith("win"):
        lib_name = "SRAL.dll"
    elif system == "darwin":
        lib_name = "libSRAL.dylib"
    else:
        lib_name = "libSRAL.so"

    # 1) Explicit path
    explicit = os.environ.get("SRAL_DLL_PATH")
    if explicit and os.path.isfile(explicit):
        return explicit

    # Helper to probe within a root directory
    def probe_root(root: Optional[str]) -> Optional[str]:
        if not root:
            return None
        candidates = [
            os.path.join(root, lib_name),
            os.path.join(root, "bin", lib_name),
            os.path.join(root, "build", lib_name),
            os.path.join(root, "build", "Release", lib_name),
            os.path.join(root, "x64", "Release", lib_name),
            os.path.join(root, "Release", lib_name),
            os.path.join(root, "out", lib_name),
            os.path.join(root, "lib", lib_name),
        ]
        for c in candidates:
            if os.path.isfile(c):
                return c
        return None

    # 2) SRAL_ROOT
    root_env = os.environ.get("SRAL_ROOT")
    found = probe_root(root_env)
    if found:
        return found

    # 3) Local 'sral' or 'SRAL' directories (gitignored)
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    for folder in ("sral", "SRAL"):
        found = probe_root(os.path.join(project_root, folder))
        if found:
            return found

    # 4) Fallback to existing behavior (src adjacent)
    fallback = os.path.join(os.path.dirname(__file__), "SRAL.dll")
    return fallback


def _load_sral_cdll() -> ctypes.CDLL:
    path = _resolve_sral_library_path()
    # On Windows, ensure the directory is in the DLL search path so dependencies are found
    if sys.platform.startswith("win"):
        dll_dir = os.path.dirname(path)
        try:
            if hasattr(os, "add_dll_directory"):
                os.add_dll_directory(dll_dir)
            else:
                os.environ["PATH"] = dll_dir + os.pathsep + os.environ.get("PATH", "")
        except Exception:
            pass
    return ctypes.CDLL(path)


class SRALWrapper:
    def __init__(self):
        # Load the SRAL shared library (from configurable locations)
        self.sral = _load_sral_cdll()

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
        
        # Add volume control function signatures
        self.sral.SRAL_SetVolume.argtypes = [ctypes.c_uint64]
        self.sral.SRAL_SetVolume.restype = ctypes.c_bool
        
        self.sral.SRAL_GetVolume.argtypes = []
        self.sral.SRAL_GetVolume.restype = ctypes.c_uint64
        
        # Initialize SRAL
        if not self.initialize():
            raise RuntimeError("Failed to initialize SRAL")
    
    def initialize(self, engines_exclude: int = 0) -> bool:
        """Initialize SRAL with optional engine exclusions."""
        success = self.sral.SRAL_Initialize(engines_exclude)
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
    
    # Legacy SAPI-specific helpers no longer supported in this SRAL version.
    def get_sapi_voices(self) -> list[str]:
        return []

    def set_sapi_voice(self, index: int) -> bool:
        return False

    def get_current_sapi_voice(self) -> int:
        return -1

    def set_rate(self, rate: int) -> bool:
        """Set the speech rate (0-100)."""
        return self.sral.SRAL_SetRate(rate)

    def get_rate(self) -> int:
        """Get the current speech rate."""
        return self.sral.SRAL_GetRate()

    def set_volume(self, volume: int) -> bool:
        """Set the speech volume (0-100)."""
        if not 0 <= volume <= 100:
            raise ValueError("Volume must be between 0 and 100")
        return self.sral.SRAL_SetVolume(volume)

    def get_volume(self) -> int:
        """Get the current speech volume."""
        return self.sral.SRAL_GetVolume()
    
    def __del__(self):
        """Clean up SRAL when the wrapper is destroyed."""
        if hasattr(self, 'sral'):
            self.sral.SRAL_Uninitialize()

class SRALEngine:
    """SRAL-based text-to-speech engine that implements the same interface as accessible_output3."""
    
    def __init__(self, speech_engine_mode="screen_reader"):
        """Initialize SRAL text-to-speech engine with specified speech engine mode."""
        # Load SRAL DLL from configurable locations
        self.sral = _load_sral_cdll()

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
            raise ValueError("Volume must be between 0 and 100")
        return self.sral.SRAL_SetVolume(volume)

    def get_volume(self) -> int:
        """Get current speech volume."""
        return self.sral.SRAL_GetVolume()

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
            success &= self.set_pitch(pitch)
            
        return success

# Example usage:
if __name__ == "__main__":
    try:
        sral = SRALWrapper()
        print(f"Current engine: {sral.get_current_engine()}")
        sral.speak("Hello, this is a test of the SRAL speech system.")
    except Exception as e:
        print(f"Error: {e}")
