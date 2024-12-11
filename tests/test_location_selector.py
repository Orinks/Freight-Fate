import pygame
import pytest
import warnings

# Suppress the pkg_resources deprecation warning from pygame
warnings.filterwarnings("ignore", category=DeprecationWarning, 
                       module="pkg_resources")
from src.game.location_selector import LocationSelector

# Initialize pygame for tests
pygame.init()
pygame.font.init()

class MockTTSEngine:
    def __init__(self):
        self.last_output = None
        
    def output(self, text):
        self.last_output = text

class MockScreen:
    def __init__(self):
        self.size = (800, 600)
        
    def get_width(self):
        return self.size[0]
        
    def get_height(self):
        return self.size[1]

def test_location_selector_space_no_locations():
    screen = MockScreen()
    tts = MockTTSEngine()
    selector = LocationSelector(screen, tts, [])
    
    # Simulate space press with no locations
    event = pygame.event.Event(pygame.KEYDOWN, {'key': pygame.K_SPACE})
    selector.handle_event(event)
    
    assert tts.last_output == "No locations available"

def test_location_selector_space_with_location():
    screen = MockScreen()
    tts = MockTTSEngine()
    
    # Sample city data
    cities_data = [{
        'name': 'Test City',
        'locations': [{
            'name': 'Test Stop',
            'type': 'truck_stop',
            'cargo_types': ['general']
        }]
    }]
    
    selector = LocationSelector(screen, tts, cities_data)
    selector.set_city('Test City')
    
    # Simulate space press with location selected
    event = pygame.event.Event(pygame.KEYDOWN, {'key': pygame.K_SPACE})
    selector.handle_event(event)
    
    assert "Test Stop" in tts.last_output
    assert "truck_stop" in tts.last_output

def teardown_module(module):
    """Clean up pygame after tests"""
    pygame.quit()
