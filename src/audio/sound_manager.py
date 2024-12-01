import pygame
import accessible_output2.outputs.auto

class SoundManager:
    def __init__(self):
        self.screen_reader = accessible_output2.outputs.auto.Auto()
        self.sounds = {}
        self._load_sounds()

    def _load_sounds(self):
        """Load all game sounds"""
        sound_files = {
            'engine_idle': 'assets/sounds/engine_idle.wav',
            'engine_accelerate': 'assets/sounds/engine_accelerate.wav',
            'weather_rain': 'assets/sounds/rain.wav',
            # Add more sounds as needed
        }
        
        # Sounds will be loaded when audio files are added
        # for name, path in sound_files.items():
        #     self.sounds[name] = pygame.mixer.Sound(path)

    def play_sound(self, sound_name, loop=False):
        """Play a sound by name"""
        if sound_name in self.sounds:
            self.sounds[sound_name].play(-1 if loop else 0)

    def speak(self, message):
        """Use screen reader to speak a message"""
        self.screen_reader.output(message)
