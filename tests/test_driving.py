"""Test script for driving mechanics."""
import os
import sys
import time
import pygame

# Add the src directory to the Python path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'src'))

from game.driving.state import DrivingState
from game.sound_manager import SoundManager
from game.settings import Settings
from sral_tts import SRALEngine

class MockSoundManager(SoundManager):
    def __init__(self):
        super().__init__()
        self.played_sounds = []
        self.current_engine_rpm = 0
        
    def play_sound(self, sound_name):
        self.played_sounds.append(sound_name)
        print(f"Playing sound: {sound_name}")
        
    def play_engine_rev(self, rpm):
        self.current_engine_rpm = rpm
        self.played_sounds.append(f"engine_rev_{rpm}")
        print(f"Engine rev at {rpm} RPM")
        
    def update_engine_sound(self, rpm, max_rpm):
        self.current_engine_rpm = rpm
        self.played_sounds.append(f"engine_update_{rpm}")
        
    def play_engine_start(self):
        self.played_sounds.append("engine_start")
        print("Playing engine start sound")
        
    def play_engine_idle(self):
        self.played_sounds.append("engine_idle")
        print("Playing engine idle sound")
        
    def play_engine_rev(self, rpm):
        self.current_engine_rpm = rpm
        self.played_sounds.append("engine_rev")
        print(f"Playing engine rev at {rpm} RPM")
        
    def play_gear_shift(self):
        self.played_sounds.append("gear_shift")
        print("Playing gear shift sound")
        
    def play_brake(self):
        self.played_sounds.append("brake")
        print("Playing brake sound")

class MockTTSEngine:
    def __init__(self):
        self.outputs = []
        
    def output(self, text):
        self.outputs.append(text)
        print(f"TTS: {text}")
        return True
        
    def stop(self):
        return True

def test_driving_controls():
    """Test basic driving controls and physics with sound/speech feedback."""
    print("\n=== Testing Driving Controls ===")
    
    # Initialize pygame
    pygame.init()
    screen = pygame.display.set_mode((800, 600))
    pygame.display.set_caption("Driving Test")
    
    # Initialize components with mock objects
    settings = Settings()
    sound_manager = MockSoundManager()
    tts_engine = MockTTSEngine()
    
    # Create driving state with test parameters
    print("Creating driving state...")
    driving_state = DrivingState(
        screen=screen,
        tts_engine=tts_engine,
        sound_manager=sound_manager,
        settings=settings,
        start_city="Test City",
        start_location={
            'name': 'Test Location',
            'type': 'warehouse',
            'cargo_types': ['general']
        }
    )
    
    # Test duration and parameters
    test_duration = 10.0  # Run test for 10 seconds
    elapsed_time = 0.0
    initial_speed = driving_state.truck.speed
    max_speed_reached = 0.0
    
    # Define test sequence of inputs with expected sounds/feedback
    key_events = [
        # Start engine and idle
        (0.1, pygame.event.Event(pygame.KEYDOWN, {"key": pygame.K_w})),  # Start accelerating
        (2.2, pygame.event.Event(pygame.KEYUP, {"key": pygame.K_w})),    # Stop accelerating
        (2.3, pygame.event.Event(pygame.KEYDOWN, {"key": pygame.K_s})),  # Start braking
        (3.0, pygame.event.Event(pygame.KEYUP, {"key": pygame.K_s})),    # Stop braking            # Shift to 2nd gear sequence
            (3.1, pygame.event.Event(pygame.KEYDOWN, {"key": pygame.K_LSHIFT})), # Press clutch
            (3.15, pygame.event.Event(pygame.KEYDOWN, {"key": pygame.K_2})),  # Press 2 key
            (3.7, pygame.event.Event(pygame.KEYUP, {"key": pygame.K_2})),    # Release 2 key
            (3.8, pygame.event.Event(pygame.KEYUP, {"key": pygame.K_LSHIFT})), # Release clutch after shift completes
        (3.4, pygame.event.Event(pygame.KEYDOWN, {"key": pygame.K_w})),  # Accelerate again
        (8.0, pygame.event.Event(pygame.KEYUP, {"key": pygame.K_w})),    # Stop accelerating
    ]
    event_index = 0
    
    # Expected sounds in order
    expected_sounds = [
        "engine_start",  # Initial engine start
        "engine_idle",   # Idle sound
        "engine_rev",    # When accelerating
        "brake",         # When braking
        "gear_shift",    # When changing gear
    ]
    
    clock = pygame.time.Clock()
    running = True
    
    while running and elapsed_time < test_duration:
        dt = clock.tick(60) / 1000.0
        elapsed_time += dt
        
        # Post scheduled events at the right times
        while (event_index < len(key_events) and 
               elapsed_time >= key_events[event_index][0]):
            pygame.event.post(key_events[event_index][1])
            event_index += 1
        
        # Process events
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            driving_state.handle_input(event)
        
        # Update and track max speed
        driving_state.update(dt)
        max_speed_reached = max(max_speed_reached, driving_state.truck.speed)
        
        # Print state for debugging
        print(f"\rTime: {elapsed_time:.1f}s | "
              f"Speed: {driving_state.truck.speed:.1f} km/h | "
              f"Gear: {driving_state.transmission.current_gear} | "
              f"RPM: {driving_state.truck.engine_rpm:.0f}", end='')
        
        driving_state.render()
        pygame.display.flip()
    
    pygame.quit()
    
    # Verify driving physics
    assert max_speed_reached > initial_speed, "Vehicle failed to accelerate"
    assert driving_state.transmission.current_gear == 2, "Failed to shift to second gear"
    
    # Verify sounds were played
    for sound in expected_sounds:
        matching_sounds = [s for s in sound_manager.played_sounds if sound in s]
        assert matching_sounds, f"Expected {sound} sound was not played"
    
    # Verify TTS feedback
    speed_announcements = [msg for msg in tts_engine.outputs if "km/h" in msg or "mph" in msg]
    gear_announcements = [msg for msg in tts_engine.outputs if "gear" in msg.lower()]
    assert speed_announcements, "No speed announcements were made"
    assert gear_announcements, "No gear change announcements were made"
    
    print("\nDriving test completed successfully.")
    print("\nSound summary:")
    print(f"Total sounds played: {len(sound_manager.played_sounds)}")
    print("Unique sounds:", set(sound_manager.played_sounds))
    print("\nTTS summary:")
    print(f"Total announcements: {len(tts_engine.outputs)}")
    print("Messages:", tts_engine.outputs)

def test_collision_detection():
    """Test collision detection with obstacles and associated sounds/feedback."""
    print("\n=== Testing Collision Detection ===")
    pygame.init()
    screen = pygame.display.set_mode((800, 600))
    pygame.display.set_caption("Collision Test")
    
    settings = Settings()
    sound_manager = MockSoundManager()
    tts_engine = MockTTSEngine()
    
    driving_state = DrivingState(
        screen=screen,
        tts_engine=tts_engine,
        sound_manager=sound_manager,
        settings=settings,
        start_city="Test City",
        start_location={
            'name': 'Test Location',
            'type': 'warehouse',
            'cargo_types': ['general']
        }
    )
    
    # Test parameters
    test_duration = 10.0
    elapsed_time = 0.0
    collision_count = 0
    obstacle_x = 400  # Obstacle position
    
    # Start with full throttle
    pygame.event.post(pygame.event.Event(pygame.KEYDOWN, {"key": pygame.K_w}))
    
    clock = pygame.time.Clock()
    running = True
    
    while running and elapsed_time < test_duration:
        dt = clock.tick(60) / 1000.0
        elapsed_time += dt
        
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            driving_state.handle_input(event)
        
        driving_state.update(dt)
        
        # Check for collision with obstacle
        if driving_state.truck.position > obstacle_x:
            collision_count += 1
            print(f"\nCollision detected at position {driving_state.truck.position:.1f}m!")
            driving_state.truck.position = 350  # Reset position
            
            # Verify collision sounds and feedback
            assert "collision" in str(sound_manager.played_sounds).lower(), "No collision sound played"
            assert any("collision" in msg.lower() for msg in tts_engine.outputs), "No collision announcement made"
        
        print(f"\rTime: {elapsed_time:.1f}s | "
              f"Position: {driving_state.truck.position:.1f}m | "
              f"Collisions: {collision_count}", end='')
        
        driving_state.render()
        pygame.display.flip()
    
    pygame.quit()
    
    # Assertions
    assert elapsed_time >= test_duration, "Test ended prematurely"
    assert collision_count > 0, "No collisions detected during test"
    
    # Sound and feedback verification
    print("\nSound summary:")
    print(f"Total sounds played: {len(sound_manager.played_sounds)}")
    print("Unique sounds:", set(sound_manager.played_sounds))
    print("\nTTS summary:")
    print(f"Total announcements: {len(tts_engine.outputs)}")
    print("Messages:", tts_engine.outputs)
