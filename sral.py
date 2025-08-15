import ctypes
from ctypes import c_bool, c_char_p, c_uint64, c_int
import platform


class Sral:
    def __init__(self, engines_exclude=0):
        system = platform.system()
        if system == "Windows":
            self.lib = ctypes.CDLL("./SRAL.dll")
        elif system == "Linux":
            self.lib = ctypes.CDLL("./libSRAL.so")
        elif system == "Darwin":  # MacOS
            self.lib = ctypes.CDLL("./libSRAL.dylib")
        else:
            raise OSError(f"Unsupported operating system: {system}")


        if not self.lib.SRAL_Initialize(c_int(engines_exclude)):
            raise RuntimeError("Failed to initialize SRAL")

    def __del__(self):
        self.lib.SRAL_Uninitialize()

    def speak(self, text, interrupt=True):
        return self.lib.SRAL_Speak(c_char_p(text.encode('utf-8')), c_bool(interrupt))

    def speak_ssml(self, text, interrupt=True):
        return self.lib.SRAL_SpeakSsml(c_char_p(text.encode('utf-8')), c_bool(interrupt))

    def braille(self, text):
        return self.lib.SRAL_Braille(c_char_p(text.encode('utf-8')))

    def output(self, text, interrupt=True):
        return self.lib.SRAL_Output(c_char_p(text.encode('utf-8')), c_bool(interrupt))

    def stop_speech(self):
        return self.lib.SRAL_StopSpeech()

    def pause_speech(self):
        return self.lib.SRAL_PauseSpeech()

    def resume_speech(self):
        return self.lib.SRAL_ResumeSpeech()

    def get_current_engine(self):
        return self.lib.SRAL_GetCurrentEngine()

    def get_engine_features(self, engine):
        return self.lib.SRAL_GetEngineFeatures(c_int(engine))

    def set_engine_parameter(self, engine, param, value):
        return self.lib.SRAL_SetEngineParameter(c_int(engine), c_int(param), c_int(value))


    def set_volume(self, value):
        return self.lib.SRAL_SetVolume(c_uint64(value))

    def get_volume(self):
        return self.lib.SRAL_GetVolume()

    def set_rate(self, value):
        return self.lib.SRAL_SetRate(c_uint64(value))

    def get_rate(self):
        return self.lib.SRAL_GetRate()

    def get_voice_count(self):
        return self.lib.SRAL_GetVoiceCount()

    def get_voice_name(self, index):
        self.lib.SRAL_GetVoiceName.restype = c_char_p
        voice_name = self.lib.SRAL_GetVoiceName(c_uint64(index))
    
        if voice_name is None:
            raise ValueError(f"No voice found at index {index}")
    
        return voice_name.decode('utf-8')

    def set_voice(self, index):
        return self.lib.SRAL_SetVoice(c_uint64(index))

    def speak_ex(self, engine, text, interrupt=True):
        return self.lib.SRAL_SpeakEx(c_int(engine), c_char_p(text.encode('utf-8')), c_bool(interrupt))

    def speak_ssml_ex(self, engine, text, interrupt=True):
        return self.lib.SRAL_SpeakSsmlEx(c_int(engine), c_char_p(text.encode('utf-8')), c_bool(interrupt))


    def braille_ex(self, engine, text):
        return self.lib.SRAL_BrailleEx(c_int(engine), c_char_p(text.encode('utf-8')))

    def output_ex(self, engine, text, interrupt=True):
        return self.lib.SRAL_OutputEx(c_int(engine), c_char_p(text.encode('utf-8')), c_bool(interrupt))

    def stop_speech_ex(self, engine):
        return self.lib.SRAL_StopSpeechEx(c_int(engine))

    def pause_speech_ex(self, engine):
        return self.lib.SRAL_PauseSpeechEx(c_int(engine))

    def resume_speech_ex(self, engine):
        return self.lib.SRAL_ResumeSpeechEx(c_int(engine))

    def set_volume_ex(self, engine, value):
        return self.lib.SRAL_SetVolumeEx(c_int(engine), c_uint64(value))

    def get_volume_ex(self, engine):
        return self.lib.SRAL_GetVolumeEx(c_int(engine))

    def set_rate_ex(self, engine, value):
        return self.lib.SRAL_SetRateEx(c_int(engine), c_uint64(value))

    def get_rate_ex(self, engine):
        return self.lib.SRAL_GetRateEx(c_int(engine))

    def get_voice_count_ex(self, engine):
        return self.lib.SRAL_GetVoiceCountEx(c_int(engine))

    def get_voice_name_ex(self, engine, index):
        self.lib.SRAL_GetVoiceName.restype = c_char_p
        voice_name = self.lib.SRAL_GetVoiceNameEx(c_int(engine), c_uint64(index))
    
        if voice_name is None:
            raise ValueError(f"No voice found at index {index}")
    
        return voice_name.decode('utf-8')


    def set_voice_ex(self, engine, index):
        return self.lib.SRAL_SetVoiceEx(c_int(engine), c_uint64(index))

    def is_initialized(self):
        return self.lib.SRAL_IsInitialized()

    def delay(self, time):
        return self.lib.SRAL_Delay(c_int(time))

    def register_keyboard_hooks(self):
        return self.lib.SRAL_RegisterKeyboardHooks()

    def unregister_keyboard_hooks(self):
        return self.lib.SRAL_UnregisterKeyboardHooks()

    def get_available_engines(self):
        return self.lib.SRAL_GetAvailableEngines()

    def get_active_engines(self):
        return self.lib.SRAL_GetActiveEngines()
