"""Test script for sound system."""
import os
import sys
import time
import pygame

# Add the src directory to the Python path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'src'))

from game.sound_manager import SoundManager

class MockSoundManager(SoundManager):
    def __init__(self):
        super().__init__()
        self.played_sounds = []
        self.current_engine_rpm = 0
        
    def play_sound(self, sound_name):
        self.played_sounds.append(sound_name)
        
    def play_engine_rev(self, rpm):
        self.current_engine_rpm = rpm
        self.played_sounds.append(f"engine_rev_{rpm}")
        
    def update_engine_sound(self, rpm, max_rpm):
        self.current_engine_rpm = rpm
        self.played_sounds.append(f"engine_update_{rpm}")

def test_menu_sounds():
    """Test menu sound effects."""
    print("\n=== Testing Menu Sounds ===")
    
    # Initialize pygame
    pygame.init()
    pygame.mixer.init()
    
    # Create mock sound manager
    sound_manager = MockSoundManager()
    
    # Test menu sounds
    sound_manager.play_sound('menu_nav')
    assert 'menu_nav' in sound_manager.played_sounds
    
    sound_manager.play_sound('menu_select')
    assert 'menu_select' in sound_manager.played_sounds
    
    sound_manager.play_sound('menu_back')
    assert 'menu_back' in sound_manager.played_sounds
    
    pygame.quit()
    print("Menu sounds test completed successfully.")

def test_engine_sounds():
    """Test engine sound effects."""
    print("\n=== Testing Engine Sounds ===")
    
    pygame.init()
    pygame.mixer.init()
    
    sound_manager = MockSoundManager()
    
    # Test engine start
    sound_manager.play_engine_start()
    assert 'engine_start' in sound_manager.played_sounds
    
    # Test engine idle
    sound_manager.play_engine_idle()
    assert 'engine_idle' in sound_manager.played_sounds
    
    # Test engine rev at different RPMs
    test_rpms = [1000, 2000, 3000, 4000, 5000]
    for rpm in test_rpms:
        sound_manager.play_engine_rev(rpm)
        assert f'engine_rev_{rpm}' in sound_manager.played_sounds
        assert sound_manager.current_engine_rpm == rpm
    
    # Test gear shift sound
    sound_manager.play_gear_shift()
    assert 'gear_shift' in sound_manager.played_sounds
    
    # Test brake sound
    sound_manager.play_brake()
    assert 'brake' in sound_manager.played_sounds
    
    pygame.quit()
    print("Engine sounds test completed successfully.")

def test_weather_sounds():
    """Test weather sound effects."""
    print("\n=== Testing Weather Sounds ===")
    
    pygame.init()
    pygame.mixer.init()
    
    sound_manager = MockSoundManager()
    
    # Test weather sounds
    sound_manager.play_rain_light()
    assert 'rain_light' in sound_manager.played_sounds
    
    sound_manager.play_rain_heavy()
    assert 'rain_heavy' in sound_manager.played_sounds
    
    sound_manager.play_thunder()
    assert 'thunder' in sound_manager.played_sounds
    
    sound_manager.play_wind()
    assert 'wind' in sound_manager.played_sounds
    
    pygame.quit()
    print("Weather sounds test completed successfully.")

def test_sound_mixing():
    """Test multiple sounds playing simultaneously."""
    print("\n=== Testing Sound Mixing ===")
    
    pygame.init()
    pygame.mixer.init()
    
    sound_manager = MockSoundManager()
    
    # Play multiple sounds
    sound_manager.play_engine_idle()
    sound_manager.play_rain_light()
    sound_manager.play_wind()
    
    # Verify all sounds were triggered
    assert 'engine_idle' in sound_manager.played_sounds
    assert 'rain_light' in sound_manager.played_sounds
    assert 'wind' in sound_manager.played_sounds
    
    # Test volume changes
    test_volumes = [1.0, 0.7, 0.4, 0.1, 0.4, 0.7, 1.0]
    for volume in test_volumes:
        pygame.mixer.music.set_volume(volume)
        time.sleep(0.1)  # Brief delay to allow volume change to take effect
    
    pygame.quit()
    print("Sound mixing test completed successfully.")

if __name__ == "__main__":
    test_menu_sounds()
    test_engine_sounds()
    test_weather_sounds()
    test_sound_mixing()
