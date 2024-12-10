import pygame
import time
import threading
from typing import Dict, Optional
from ..settings import Settings
from .vehicle import TruckPhysics
from .transmission import Transmission
from .sound_effects import SoundEffects

class AudioHUD:
    def __init__(self, tts_engine, truck: TruckPhysics, transmission: Transmission, settings: Settings):
        """Initialize the audio HUD.
        
        Args:
            tts_engine: Text-to-speech engine from main game
            truck: TruckPhysics instance for vehicle state
            transmission: Transmission instance for gear state
            settings: Settings instance for unit preferences
        """
        self.truck = truck
        self.transmission = transmission
        self.tts_engine = tts_engine
        self.settings = settings
        
        # Initialize sound effects
        self.sound_fx = SoundEffects()
        
        # Thread safety for TTS engine
        self.tts_lock = threading.Lock()
        
        # State tracking to avoid repetitive announcements
        self.last_announcement_time: Dict[str, float] = {}
        self.last_values = {
            'speed': 0,
            'gear': 1,
            'warnings': set(),
            'fuel': 100,
            'engine_running': False
        }
        
        # Keyboard shortcuts
        self.shortcuts = {
            pygame.K_F5: self.announce_status,  # F5 for full status
            pygame.K_F6: self.announce_speed,   # F6 for current speed
            pygame.K_F7: self.announce_fuel,    # F7 for fuel status
            pygame.K_F8: self.announce_warnings # F8 for active warnings
        }
        
        # Cooldown times (in seconds) for different announcements
        self.cooldowns = {
            'speed': 5.0,
            'gear': 0.0,  # No cooldown for gear changes
            'warning': 15.0,
            'fuel': 30.0,
            'status': 10.0
        }
        
        # Configure different voices for different types of feedback
        self.voices = None
        self.warning_voice = None
    
    def handle_input(self, event: pygame.event.Event):
        """Handle keyboard shortcuts for audio feedback."""
        if event.type == pygame.KEYDOWN:
            print(f"AudioHUD received key: {event.key}")  # Debug output
            if event.key in self.shortcuts:
                print(f"AudioHUD executing shortcut for key: {event.key}")  # Debug output
                self.sound_fx.play_ui_sound()
                self.shortcuts[event.key]()
                return True
        return False
    
    def announce_speed(self):
        """Announce current speed."""
        if not self._can_announce('speed'):
            return
            
        speed_kph = self.truck.get_speed_kph()
        speed = self.settings.convert_speed(speed_kph)
        unit = self.settings.get_speed_unit()
        self.speak(f"Speed: {speed:.0f} {unit}")
        self._update_last_announcement('speed')
    
    def announce_fuel(self):
        """Announce fuel status on demand."""
        status = self.truck.get_status()
        self.speak(f"Fuel level at {int(status['fuel'])} percent")
    
    def announce_warnings(self):
        """Announce all active warnings."""
        status = self.truck.get_status()
        active_warnings = [
            name for name, active in status['warnings'].items() if active
        ]
        
        if not active_warnings:
            self.speak("No active warnings")
            return
            
        warning_messages = {
            'engine_temp': "Engine temperature critical",
            'brake_temp': "Brake temperature critical",
            'low_fuel': "Fuel level low",
            'tire_wear': "Tire wear critical"
        }
        
        warnings_text = ". ".join(
            warning_messages[warning] for warning in active_warnings
        )
        self.speak(f"Active warnings: {warnings_text}", warning=True)
    
    def update_engine_sounds(self, status: Dict):
        """Update engine sound effects based on vehicle state."""
        rpm_normalized = status['rpm'] / 3000  # Normalize to 0-1 range
        load = status['speed'] / 140  # Simple load calculation
        
        # Start/stop engine sounds
        if status['speed'] > 0 and not self.last_values['engine_running']:
            self.sound_fx.play_engine_sound(rpm_normalized, load)
            self.last_values['engine_running'] = True
        elif status['speed'] == 0 and self.last_values['engine_running']:
            self.sound_fx.stop_engine_sound()
            self.last_values['engine_running'] = False
        
        # Update engine sound mix
        if self.last_values['engine_running']:
            self.sound_fx.play_engine_sound(rpm_normalized, load)
    
    def update_warning_sounds(self, warnings: Dict[str, bool]):
        """Update warning sound effects."""
        current_warnings = {
            name for name, active in warnings.items() if active
        }
        
        # Play warning sounds for new warnings
        new_warnings = current_warnings - self.last_values['warnings']
        if new_warnings:
            if 'engine_temp' in new_warnings or 'brake_temp' in new_warnings:
                self.sound_fx.play_warning('temp')
            if 'low_fuel' in new_warnings:
                self.sound_fx.play_warning('fuel')
            if 'tire_wear' in new_warnings:
                self.sound_fx.play_warning('general')
    
    def speak(self, text: str, warning: bool = False) -> None:
        """Thread-safe speaking function."""
        print(f"AudioHUD speaking: {text}")  # Debug output
        with self.tts_lock:
            if self.tts_engine:
                print("AudioHUD calling tts_engine.output")  # Debug output
                self.tts_engine.output(text)
            else:
                print("AudioHUD: No TTS engine available!")  # Debug output
    
    def _can_announce(self, announcement_type: str) -> bool:
        """Check if enough time has passed to make another announcement."""
        current_time = time.time()
        last_time = self.last_announcement_time.get(announcement_type, 0)
        return current_time - last_time >= self.cooldowns[announcement_type]
    
    def _update_last_announcement(self, announcement_type: str):
        """Update the last announcement time."""
        self.last_announcement_time[announcement_type] = time.time()
    
    def update_speed_feedback(self, current_speed: float):
        """Provide speed feedback when it changes significantly."""
        if not self._can_announce('speed'):
            return
            
        # Only announce speed changes of 10 KPH or more
        speed_diff = abs(current_speed - self.last_values['speed'])
        if speed_diff >= 10:
            speed = self.settings.convert_speed(current_speed)
            unit = self.settings.get_speed_unit()
            self.speak(f"{speed:.0f} {unit}")
            self.last_values['speed'] = current_speed
            self._update_last_announcement('speed')
    
    def update_gear_feedback(self, current_gear: int, shift_state: str):
        """Provide feedback on gear changes and shifting state."""
        if current_gear != self.last_values['gear']:
            if shift_state == 'SHIFTING':
                self.speak(f"Shifting to gear {current_gear}")
            else:
                self.speak(f"Gear {current_gear}")
            self.last_values['gear'] = current_gear
    
    def update_warning_feedback(self, warnings: Dict[str, bool]):
        """Provide feedback for active warnings."""
        if not self._can_announce('warning'):
            return
            
        current_warnings = {
            name for name, active in warnings.items() if active
        }
        
        # Announce new warnings
        new_warnings = current_warnings - self.last_values['warnings']
        if new_warnings:
            warning_messages = {
                'engine_temp': "Warning: Engine temperature critical",
                'brake_temp': "Warning: Brake temperature critical",
                'low_fuel': "Warning: Fuel level low",
                'tire_wear': "Warning: Tire wear critical"
            }
            
            for warning in new_warnings:
                self.speak(warning_messages[warning], warning=True)
            
            self.last_values['warnings'] = current_warnings
            self._update_last_announcement('warning')
    
    def update_fuel_feedback(self, fuel_level: float):
        """Provide periodic fuel level updates."""
        if not self._can_announce('fuel'):
            return
            
        # Announce fuel level at 25% intervals or when low
        if fuel_level <= 10 and self.last_values['fuel'] > 10:
            self.speak("Fuel level critical. Less than 10 percent remaining.", warning=True)
            self._update_last_announcement('fuel')
        elif int(fuel_level / 25) < int(self.last_values['fuel'] / 25):
            self.speak(f"Fuel at {int(fuel_level)} percent")
            self._update_last_announcement('fuel')
        
        self.last_values['fuel'] = fuel_level
    
    def announce_status(self):
        """Announce full vehicle status."""
        if not self._can_announce('status'):
            return
            
        speed_kph = self.truck.get_speed_kph()
        speed = self.settings.convert_speed(speed_kph)
        speed_unit = self.settings.get_speed_unit()
        
        status_text = (
            f"Current speed: {speed:.0f} {speed_unit}. "
            f"Gear: {self.transmission.current_gear}. "
            f"RPM: {self.truck.engine_rpm:.0f}. "
            f"Fuel: {self.truck.fuel_level:.0f} percent."
        )
        
        self.speak(status_text)
        self._update_last_announcement('status')
    
    def update(self, dt):
        """Update all audio feedback systems.
        
        Args:
            dt: Time delta since last update in seconds
        """
        status = self.truck.get_status()
        transmission_state = self.transmission.get_state()
        
        # Speed announcements
        speed_kph = self.truck.get_speed_kph()
        speed = self.settings.convert_speed(speed_kph)
        
        # Announce speed at regular intervals or significant changes
        current_time = time.time()
        if current_time - self.last_announcement_time.get('speed', 0) > 10.0:  # Every 10 seconds
            self.announce_speed()
            self.last_announcement_time['speed'] = current_time
        
        # Update sound effects
        self.update_engine_sounds(status)
        self.update_warning_sounds(status['warnings'])
        
        # Update speech feedback
        self.update_speed_feedback(speed_kph)
        self.update_gear_feedback(transmission_state['gear'], transmission_state['state'])
        self.update_warning_feedback(status['warnings'])
        self.update_fuel_feedback(status['fuel'])
        
        # Play gear shift sound if gear changed
        if transmission_state['gear'] != self.last_values['gear']:
            self.sound_fx.play_gear_shift()
    
    def cleanup(self):
        """Clean up audio resources."""
        self.sound_fx.cleanup()
    
    def set_voice_rate(self, rate: int):
        """Adjust the speech rate (words per minute)."""
        pass
    
    def set_voice_volume(self, volume: float):
        """Adjust the speech volume (0.0 to 1.0)."""
        pass
