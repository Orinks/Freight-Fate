"""Test script for weather system."""
import os
import sys
import time
import pygame

# Add the src directory to the Python path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'src'))

from game.weather.weather_manager import WeatherManager
from game.sound_manager import SoundManager
from game.settings import Settings

class MockSoundManager(SoundManager):
    def __init__(self):
        super().__init__()
        self.played_sounds = []
        
    def play_sound(self, sound_name):
        self.played_sounds.append(sound_name)

def test_weather_transitions():
    """Test weather state transitions."""
    print("\n=== Testing Weather Transitions ===")
    
    pygame.init()
    screen = pygame.display.set_mode((800, 600))
    pygame.display.set_caption("Weather Test")
    
    sound_manager = MockSoundManager()
    weather_manager = WeatherManager(sound_manager)
    
    # Test parameters
    test_duration = 10.0
    elapsed_time = 0.0
    weather_duration = 2.0  # Seconds per weather state
    
    weather_states = [
        "clear",
        "light_rain",
        "heavy_rain",
        "thunderstorm"
    ]
    current_state_index = 0
    
    clock = pygame.time.Clock()
    running = True
    state_timer = 0.0
    
    while running and elapsed_time < test_duration:
        dt = clock.tick(60) / 1000.0
        elapsed_time += dt
        state_timer += dt
        
        # Change weather every few seconds
        if state_timer >= weather_duration:
            state_timer = 0.0
            current_state_index = (current_state_index + 1) % len(weather_states)
            new_state = weather_states[current_state_index]
            print(f"\nChanging weather to: {new_state}")
            weather_manager.set_weather(new_state)
            
            # Verify weather changed correctly
            assert weather_manager.current_weather == new_state, f"Weather failed to change to {new_state}"
        
        # Update and render weather
        weather_manager.update(dt)
        screen.fill((0, 0, 0))
        weather_manager.render(screen)
        pygame.display.flip()
    
    pygame.quit()
    print("\nWeather transition test completed successfully.")

def test_weather_effects():
    """Test weather visual and gameplay effects."""
    print("\n=== Testing Weather Effects ===")
    
    pygame.init()
    screen = pygame.display.set_mode((800, 600))
    pygame.display.set_caption("Weather Effects Test")
    
    sound_manager = MockSoundManager()
    weather_manager = WeatherManager(sound_manager)
    
    # Test each weather state
    weather_states = ["clear", "light_rain", "heavy_rain", "thunderstorm"]
    
    for weather in weather_states:
        print(f"\nTesting weather: {weather}")
        weather_manager.set_weather(weather)
        
        # Run for a short duration to test effects
        test_duration = 2.0
        elapsed_time = 0.0
        clock = pygame.time.Clock()
        
        while elapsed_time < test_duration:
            dt = clock.tick(60) / 1000.0
            elapsed_time += dt
            
            weather_manager.update(dt)
            screen.fill((0, 0, 0))
            weather_manager.render(screen)
            pygame.display.flip()
            
            # Verify weather effects
            effects = weather_manager.get_visual_effects()
            gameplay_effects = weather_manager.get_gameplay_effects()
            
            # Assert appropriate effects are present
            if weather != "clear":
                assert effects, f"No visual effects for {weather}"
                assert gameplay_effects, f"No gameplay effects for {weather}"
    
    pygame.quit()
    print("\nWeather effects test completed successfully.")

if __name__ == "__main__":
    test_weather_transitions()
    test_weather_effects()
