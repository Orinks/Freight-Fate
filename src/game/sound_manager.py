import os
import pygame
import wave

class SoundManager:
    def __init__(self, volume=0.5):
        """Initialize the sound manager."""
        self.sounds = {}
        self.volume = max(0.0, min(1.0, volume))  # Clamp between 0 and 1
        self.enabled = True
        self.engine_channel = None
        self.music_channel = None
        
        try:
            # Initialize pygame mixer
            if not pygame.mixer.get_init():
                pygame.mixer.pre_init(44100, -16, 2, 2048)
                pygame.mixer.init()
            print("Sound system initialized successfully")
            print(f"Mixer settings: {pygame.mixer.get_init()}")
            
            # Reserve channels for music and engine
            pygame.mixer.set_reserved(2)  # Reserve first 2 channels
            self.engine_channel = pygame.mixer.Channel(0)
            self.music_channel = pygame.mixer.Channel(1)
        except Exception as e:
            print(f"Failed to initialize sound system: {e}")
            self.enabled = False
            
        self.load_sounds()
        
    def load_sounds(self):
        """Load all sound effects."""
        if not self.enabled:
            print("! Sound system disabled, skipping sound loading")
            return
            
        # Get the absolute path to the sounds directory
        current_file = os.path.abspath(__file__)  # Get path to sound_manager.py
        src_dir = os.path.dirname(os.path.dirname(current_file))  # Go up to src directory
        project_root = os.path.dirname(src_dir)  # Go up to project root
        sounds_dir = os.path.join(project_root, 'assets', 'sounds')
        
        print(f"\nSound file paths:")
        print(f"- Current file: {current_file}")
        print(f"- Src directory: {src_dir}")
        print(f"- Project root: {project_root}")
        print(f"- Sounds directory: {sounds_dir}")
        
        # List all files in the sounds directory
        if os.path.exists(sounds_dir):
            print("\nFiles in sounds directory:")
            for file in os.listdir(sounds_dir):
                print(f"- {file}")
        else:
            print(f"! Sounds directory not found: {sounds_dir}")
        
        # Define sound effects with their filenames
        sound_files = {
            'menu_nav': 'menu_nav.wav',
            'menu_select': 'menu_select.wav',
            'menu_back': 'menu_nav.wav',  # Reuse menu_nav sound for back action
            'engine_idle': os.path.join('engine', 'idle.wav'),
            'menu_music': os.path.join('music', 'menu.wav')  # Can also be menu.ogg
        }
        
        # Load each sound file
        for sound_name, filename in sound_files.items():
            try:
                # First try the specified extension
                sound_path = os.path.join(sounds_dir, filename)
                
                # For music files, also try .ogg if .wav doesn't exist
                if sound_name == 'menu_music' and not os.path.exists(sound_path):
                    ogg_path = os.path.join(sounds_dir, 'music', 'menu.ogg')
                    if os.path.exists(ogg_path):
                        sound_path = ogg_path
                
                print(f"\nProcessing {sound_name}:")
                print(f"- Full path: {sound_path}")
                print(f"- File exists: {os.path.exists(sound_path)}")
                
                if not os.path.exists(sound_path):
                    print(f"! Sound file not found: {sound_path}")
                    self.sounds[sound_name] = None  # Store None instead of failing
                    continue
                    
                # Check if WAV file is valid (skip for OGG files)
                if sound_path.lower().endswith('.wav'):
                    try:
                        with wave.open(sound_path, 'rb') as wav_file:
                            params = wav_file.getparams()
                            print(f"- WAV file parameters for {filename}:")
                            print(f"  * Channels: {params.nchannels}")
                            print(f"  * Sample width: {params.sampwidth}")
                            print(f"  * Framerate: {params.framerate}")
                            print(f"  * Frames: {params.nframes}")
                    except Exception as wav_error:
                        print(f"! Invalid WAV file {filename}: {wav_error}")
                        continue
                
                # Try to load the sound
                print("- Loading sound into pygame...")
                sound = pygame.mixer.Sound(sound_path)
                sound.set_volume(self.volume)
                self.sounds[sound_name] = sound
                print(f"Successfully loaded {sound_name}")
                
            except Exception as e:
                print(f"! Failed to load sound {sound_name}: {e}")
                
    def play_sound(self, sound_name: str):
        """Play a sound effect by name."""
        if not self.enabled:
            return
            
        if sound_name in self.sounds and self.sounds[sound_name] is not None:
            try:
                print(f"\nPlaying sound: {sound_name}")
                print(f"- Mixer busy: {pygame.mixer.get_busy()}")
                print(f"- Available channels: {pygame.mixer.get_num_channels()}")
                
                channel = self.sounds[sound_name].play()
                if channel is None:
                    print(f"! No free channel to play sound {sound_name}")
                else:
                    print(f"Playing {sound_name} on channel {channel}")
            except Exception as e:
                print(f"! Failed to play sound {sound_name}: {e}")
        else:
            print(f"! Sound not found: {sound_name}")
                
    def set_volume(self, volume: float):
        """Set volume for all sounds (0.0 to 1.0)."""
        if not self.enabled:
            return
            
        self.volume = max(0.0, min(1.0, volume))
        for sound in self.sounds.values():
            sound.set_volume(self.volume)
            
    def stop_all(self):
        """Stop all currently playing sounds."""
        if not self.enabled:
            return
            
        try:
            pygame.mixer.stop()
        except Exception as e:
            print(f"Failed to stop sounds: {e}")
            
    def get_debug_info(self):
        """Get debug information about the sound system."""
        info = {
            "Enabled": self.enabled,
            "Volume": self.volume,
            "Mixer Initialized": pygame.mixer.get_init() is not None,
            "Loaded Sounds": list(self.sounds.keys()),
            "Available Channels": pygame.mixer.get_num_channels() if self.enabled else 0
        }
        return info

    def play_menu_music(self):
        """Start playing menu background music with smooth looping."""
        if not self.enabled or 'menu_music' not in self.sounds:
            return
            
        try:
            print("\nStarting menu music")
            # Set volume before playing to avoid initial volume spike
            self.music_channel.set_volume(self.volume * 8.0)  # Keep the 8x volume boost
            # Start playing with infinite loops (-1)
            self.music_channel.play(self.sounds['menu_music'], loops=-1, fade_ms=100)
        except Exception as e:
            print(f"! Failed to play menu music: {e}")
            
    def stop_menu_music(self):
        """Stop menu background music with fade out."""
        if not self.enabled:
            return
            
        try:
            print("\nStopping menu music")
            self.music_channel.fadeout(1000)  # 1 second fade out
        except Exception as e:
            print(f"! Failed to stop menu music: {e}")
            
    def play_engine_idle(self):
        """Start playing engine idle sound."""
        if not self.enabled or 'engine_idle' not in self.sounds:
            return
            
        try:
            print("\nStarting engine sound")
            self.engine_channel.play(self.sounds['engine_idle'], loops=-1)
            self.engine_channel.set_volume(self.volume * 0.7)
        except Exception as e:
            print(f"! Failed to play engine sound: {e}")
            
    def update_engine_sound(self, current_rpm: float, max_rpm: float):
        """Update engine sound based on RPM."""
        if not self.enabled or not self.engine_channel:
            return
            
        try:
            # Calculate volume and pitch based on RPM
            rpm_factor = current_rpm / max_rpm
            volume = self.volume * (0.7 + (rpm_factor * 0.3))  # 70-100% volume
            self.engine_channel.set_volume(volume)
            
            # Note: Pygame's mixer doesn't support real-time pitch shifting
            # We could pre-load different pitch variants if needed
        except Exception as e:
            print(f"! Failed to update engine sound: {e}")
            
    def stop_engine_sound(self):
        """Stop engine sound."""
        if not self.enabled:
            return
            
        try:
            print("\nStopping engine sound")
            self.engine_channel.fadeout(500)  # 0.5 second fade out
        except Exception as e:
            print(f"! Failed to stop engine sound: {e}")
