import pygame
import math
from typing import Dict, Optional
from pathlib import Path

class SoundEffects:
    def __init__(self):
        pygame.mixer.init()
        self.sounds: Dict[str, pygame.mixer.Sound] = {}
        self.channels: Dict[str, pygame.mixer.Channel] = {}
        
        # Reserve channels for different sound types
        self.channels['engine'] = pygame.mixer.Channel(0)
        self.channels['warnings'] = pygame.mixer.Channel(1)
        self.channels['transmission'] = pygame.mixer.Channel(2)
        self.channels['ui'] = pygame.mixer.Channel(3)
        
        # Load sound effects
        sound_dir = Path(__file__).parent / "sounds"
        sound_dir.mkdir(exist_ok=True)
        
        # Define sound mappings (these files will need to be added to the sounds directory)
        self.sound_files = {
            'engine_idle': 'engine_idle.wav',
            'engine_rev': 'engine_rev.wav',
            'gear_shift': 'gear_shift.wav',
            'warning_beep': 'warning_beep.wav',
            'brake_squeal': 'brake_squeal.wav',
            'ui_click': 'ui_click.wav',
            'low_fuel': 'low_fuel.wav',
            'critical_temp': 'critical_temp.wav'
        }
        
        # Load available sounds
        for sound_id, filename in self.sound_files.items():
            sound_path = sound_dir / filename
            if sound_path.exists():
                self.sounds[sound_id] = pygame.mixer.Sound(str(sound_path))
    
    def play_engine_sound(self, rpm: float, load: float):
        """
        Dynamically mix engine sounds based on RPM and load.
        rpm: Engine RPM (0.0 to 1.0)
        load: Engine load (0.0 to 1.0)
        """
        if 'engine_idle' in self.sounds and 'engine_rev' in self.sounds:
            # Crossfade between idle and rev sounds based on RPM
            idle_vol = 1.0 - rpm
            rev_vol = rpm
            
            # Adjust volume based on load
            idle_vol *= 0.5 + (load * 0.5)
            rev_vol *= load
            
            # Play both sounds on the engine channel
            self.channels['engine'].set_volume(idle_vol)
            self.sounds['engine_idle'].play(-1, fade_ms=100)
            
            self.channels['engine'].set_volume(rev_vol)
            self.sounds['engine_rev'].play(-1, fade_ms=100)
    
    def stop_engine_sound(self):
        """Stop all engine sounds."""
        self.channels['engine'].stop()
    
    def play_gear_shift(self):
        """Play gear shifting sound."""
        if 'gear_shift' in self.sounds:
            self.channels['transmission'].play(self.sounds['gear_shift'])
    
    def play_warning(self, warning_type: str, continuous: bool = False):
        """
        Play warning sounds.
        warning_type: Type of warning ('temp', 'fuel', etc.)
        continuous: If True, loop the warning sound
        """
        sound_mapping = {
            'temp': 'critical_temp',
            'fuel': 'low_fuel',
            'general': 'warning_beep'
        }
        
        sound_id = sound_mapping.get(warning_type, 'warning_beep')
        if sound_id in self.sounds:
            loops = -1 if continuous else 0
            self.channels['warnings'].play(self.sounds[sound_id], loops)
    
    def stop_warning(self):
        """Stop all warning sounds."""
        self.channels['warnings'].stop()
    
    def play_brake_sound(self, intensity: float):
        """Play brake sound with variable intensity."""
        if 'brake_squeal' in self.sounds:
            volume = min(1.0, intensity)
            self.sounds['brake_squeal'].set_volume(volume)
            self.channels['warnings'].play(self.sounds['brake_squeal'])
    
    def play_ui_sound(self):
        """Play UI interaction sound."""
        if 'ui_click' in self.sounds:
            self.channels['ui'].play(self.sounds['ui_click'])
    
    def set_master_volume(self, volume: float):
        """Set master volume for all sounds."""
        for channel in self.channels.values():
            channel.set_volume(volume)
    
    def cleanup(self):
        """Stop all sounds and clean up resources."""
        pygame.mixer.stop()
        for sound in self.sounds.values():
            sound.stop()
