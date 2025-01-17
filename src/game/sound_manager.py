import os
import math
import array
import pygame

class SoundManager:
    def __init__(self, volume=0.2):
        """Initialize the sound system."""
        self.enabled = True
        self.volume = volume
        
        # Initialize pygame mixer if not already done
        if not pygame.mixer.get_init():
            pygame.mixer.init(44100, -16, 2, 2048)
        
        # Reserve channels for engine sounds
        pygame.mixer.set_num_channels(16)  # Ensure we have enough channels
        self.engine_low_channel = pygame.mixer.Channel(2)
        self.engine_mid_channel = pygame.mixer.Channel(3)
        self.engine_high_channel = pygame.mixer.Channel(4)
        
        # Dictionary to store loaded sounds
        self.sounds = {}
        
        # Load all sound effects
        self.load_sounds()
        
        print("Sound system initialized successfully")
        print(f"Mixer settings: {pygame.mixer.get_init()}")
        
    def load_sounds(self):
        """Load all sound effects."""
        # Get paths
        current_file = os.path.abspath(__file__)
        src_dir = os.path.dirname(os.path.dirname(current_file))
        project_root = os.path.dirname(src_dir)
        sounds_dir = os.path.join(project_root, 'assets', 'sounds')
        
        print("\nSound file paths:")
        print(f"- Current file: {current_file}")
        print(f"- Src directory: {src_dir}")
        print(f"- Project root: {project_root}")
        print(f"- Sounds directory: {sounds_dir}")
        
        # Define sound files to load
        sound_files = {
            'menu_nav': os.path.join(sounds_dir, 'menu_nav.wav'),
            'menu_select': os.path.join(sounds_dir, 'menu_select.wav'),
            'menu_back': os.path.join(sounds_dir, 'menu_back.wav'),
            'menu_music': os.path.join(sounds_dir, 'music', 'menu.ogg'),
            'engine_idle': os.path.join(sounds_dir, 'engine', 'idle.wav'),
            'engine_low': os.path.join(sounds_dir, 'engine', 'low.wav'),
            'engine_mid': os.path.join(sounds_dir, 'engine', 'mid.wav'),
            'engine_high': os.path.join(sounds_dir, 'engine', 'high.wav'),
            'engine_rev': os.path.join(sounds_dir, 'engine', 'rev.wav'),
            'engine_start': os.path.join(sounds_dir, 'engine', 'start.wav'),
            'gear_shift': os.path.join(sounds_dir, 'vehicle', 'gear_shift.wav'),
            'brake': os.path.join(sounds_dir, 'vehicle', 'brake.wav'),
            'tire_screech': os.path.join(sounds_dir, 'vehicle', 'tire_screech.wav'),
            'collision': os.path.join(sounds_dir, 'vehicle', 'collision.wav'),
            'rain_light': os.path.join(sounds_dir, 'weather', 'rain_light.wav'),
            'rain_heavy': os.path.join(sounds_dir, 'weather', 'rain_heavy.wav'),
            'thunder': os.path.join(sounds_dir, 'weather', 'thunder.wav'),
            'wind': os.path.join(sounds_dir, 'weather', 'wind.wav'),
        }
        
        # Load each sound file
        for name, path in sound_files.items():
            print(f"\nProcessing {name}:")
            print(f"- Full path: {path}")
            print(f"- File exists: {os.path.exists(path)}")
            
            try:
                if os.path.exists(path):
                    self.sounds[name] = pygame.mixer.Sound(path)
                    print("- Sound loaded successfully")
                else:
                    # Create placeholder sounds for missing engine sounds
                    if name.startswith('engine_'):
                        # Create simple tones at different frequencies for engine sounds
                        if name == 'engine_low':
                            self.sounds[name] = self.create_placeholder_sound(220)  # A3
                        elif name == 'engine_mid':
                            self.sounds[name] = self.create_placeholder_sound(440)  # A4
                        elif name == 'engine_high':
                            self.sounds[name] = self.create_placeholder_sound(880)  # A5
                        else:
                            self.sounds[name] = self.create_placeholder_sound(440)
                    else:
                        self.sounds[name] = self.create_placeholder_sound(440)
                    print(f"! Sound file not found: {path}, using placeholder")
            except Exception as e:
                print(f"! Error loading sound {name}: {e}")
                self.sounds[name] = self.create_placeholder_sound(440)
        
        print("\nDebug info:")
        print(f"- Enabled: {self.enabled}")
        print(f"- Volume: {self.volume}")
        print(f"- Mixer Initialized: {bool(pygame.mixer.get_init())}")
        print(f"- Loaded Sounds: {list(self.sounds.keys())}")
        print(f"- Available Channels: {pygame.mixer.get_num_channels()}")
    
    def create_placeholder_sound(self, frequency):
        """Create a simple placeholder sound."""
        sample_rate = 44100
        duration = 1.0  # seconds
        
        # Generate a simple sine wave
        samples = []
        for i in range(int(duration * sample_rate)):
            sample = int(32767.0 * math.sin(2.0 * math.pi * frequency * i / sample_rate))
            samples.append(sample)
        
        # Convert to bytes
        sample_array = array.array('h', samples)
        return pygame.mixer.Sound(sample_array)
    
    def update_engine_sound(self, current_rpm: float, max_rpm: float):
        """Update engine sound based on RPM."""
        if not self.enabled:
            return
        
        rpm_fraction = current_rpm / max_rpm
        
        # Calculate volumes for each engine sound layer
        vol_low = max(0.0, 1.0 - (rpm_fraction * 2.0))
        vol_mid = max(0.0, 1.0 - abs(rpm_fraction * 2.0 - 1.0))
        vol_high = max(0.0, (rpm_fraction * 2.0 - 1.0))
        
        # Scale by master volume
        vol_low *= self.volume
        vol_mid *= self.volume
        vol_high *= self.volume
        
        # Start playing if not already
        if not self.engine_low_channel.get_busy():
            self.engine_low_channel.play(self.sounds["engine_low"], loops=-1)
        if not self.engine_mid_channel.get_busy():
            self.engine_mid_channel.play(self.sounds["engine_mid"], loops=-1)
        if not self.engine_high_channel.get_busy():
            self.engine_high_channel.play(self.sounds["engine_high"], loops=-1)
        
        # Set volumes
        self.engine_low_channel.set_volume(vol_low)
        self.engine_mid_channel.set_volume(vol_mid)
        self.engine_high_channel.set_volume(vol_high)
    
    def play_sound(self, sound_name):
        """Play a sound effect."""
        if not self.enabled or sound_name not in self.sounds:
            return
            
        print(f"\nPlaying sound: {sound_name}")
        print(f"- Mixer busy: {pygame.mixer.get_busy()}")
        print(f"- Available channels: {pygame.mixer.get_num_channels()}")
        
        channel = pygame.mixer.find_channel()
        if channel:
            channel.set_volume(self.volume)
            channel.play(self.sounds[sound_name])
            print(f"Playing {sound_name} on channel {channel}")
        else:
            print("No available channel to play sound")
    
    def play_engine_start(self):
        """Play the engine start sound."""
        print("\nStarting engine sound")
        if self.enabled and 'engine_start' in self.sounds:
            channel = pygame.mixer.find_channel()
            if channel:
                channel.set_volume(self.volume)
                channel.play(self.sounds['engine_start'])
    
    def play_engine_idle(self):
        """Play the engine idle sound."""
        if self.enabled and 'engine_idle' in self.sounds:
            self.engine_low_channel.play(self.sounds['engine_idle'], loops=-1)
    
    def play_engine_rev(self, rpm):
        """Play engine rev sound based on RPM."""
        if not self.enabled:
            return
            
        # Use RPM to determine which sound to play
        if rpm < 1000:
            sound = self.sounds['engine_low']
        elif rpm < 2000:
            sound = self.sounds['engine_mid']
        else:
            sound = self.sounds['engine_high']
            
        channel = pygame.mixer.find_channel()
        if channel:
            channel.set_volume(self.volume)
            channel.play(sound)
            print(f"Playing engine rev at {rpm} RPM")
    
    def play_gear_shift(self):
        """Play gear shift sound."""
        self.play_sound('gear_shift')
    
    def play_brake(self):
        """Play brake sound."""
        self.play_sound('brake')
    
    def play_tire_screech(self):
        """Play tire screech sound."""
        self.play_sound('tire_screech')
    
    def play_collision(self):
        """Play collision sound."""
        self.play_sound('collision')
    
    def play_rain_light(self):
        """Play light rain sound."""
        self.play_sound('rain_light')
    
    def play_rain_heavy(self):
        """Play heavy rain sound."""
        self.play_sound('rain_heavy')
    
    def play_thunder(self):
        """Play thunder sound."""
        self.play_sound('thunder')
    
    def play_wind(self):
        """Play wind sound."""
        self.play_sound('wind')
    
    def play_menu_music(self):
        """Play menu music."""
        print("\nStarting menu music")
        if self.enabled and 'menu_music' in self.sounds:
            pygame.mixer.music.load(os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'assets', 'sounds', 'music', 'menu.ogg'))
            pygame.mixer.music.set_volume(self.volume)
            pygame.mixer.music.play(-1)
    
    def stop_menu_music(self):
        """Stop menu music."""
        print("\nStopping menu music")
        pygame.mixer.music.stop()
    
    def stop_all(self):
        """Stop all sounds."""
        pygame.mixer.stop()
        pygame.mixer.music.stop()
    
    def get_debug_info(self):
        """Get debug information about sound system state."""
        return {
            'enabled': self.enabled,
            'volume': self.volume,
            'mixer_initialized': bool(pygame.mixer.get_init()),
            'loaded_sounds': list(self.sounds.keys()),
            'available_channels': pygame.mixer.get_num_channels()
        }
