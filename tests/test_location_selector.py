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
        self.outputs = []
        
    def output(self, text):
        self.last_output = text
        self.outputs.append(text)

class MockScreen:
    def __init__(self):
        self.size = (800, 600)
        
    def get_width(self):
        return self.size[0]
        
    def get_height(self):
        return self.size[1]

def test_location_selector_navigation():
    """Test location navigation without manual input."""
    screen = MockScreen()
    tts = MockTTSEngine()
    
    # Sample city data with multiple locations
    cities_data = [{
        'name': 'Test City',
        'locations': [
            {
                'name': 'Test Stop 1',
                'type': 'truck_stop',
                'cargo_types': ['general']
            },
            {
                'name': 'Test Stop 2',
                'type': 'freight_terminal',
                'cargo_types': ['container']
            }
        ]
    }]
    
    selector = LocationSelector(screen, tts, cities_data)
    selector.set_city('Test City')
    
    # Test navigation down
    selector.handle_event(pygame.event.Event(pygame.KEYDOWN, {'key': pygame.K_DOWN}))
    assert "Test Stop 2" in tts.last_output
    
    # Test navigation up
    selector.handle_event(pygame.event.Event(pygame.KEYDOWN, {'key': pygame.K_UP}))
    assert "Test Stop 1" in tts.last_output
    
    # Test selection
    result = selector.handle_event(pygame.event.Event(pygame.KEYDOWN, {'key': pygame.K_RETURN}))
    assert result is not None
    assert "Test Stop 1" in tts.last_output

def test_location_selector_empty():
    """Test location selector behavior with no locations."""
    screen = MockScreen()
    tts = MockTTSEngine()
    selector = LocationSelector(screen, tts, [])
    
    # Test space press with no locations
    selector.handle_event(pygame.event.Event(pygame.KEYDOWN, {'key': pygame.K_SPACE}))
    assert "No locations available" in tts.last_output

def test_location_selector_with_location():
    """Test location selector with a valid location."""
    screen = MockScreen()
    tts = MockTTSEngine()
    
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
    
    # Test space selection
    selector.handle_event(pygame.event.Event(pygame.KEYDOWN, {'key': pygame.K_SPACE}))
    assert "Test Stop" in tts.last_output
    assert "truck_stop" in tts.last_output

def teardown_module(module):
    """Clean up pygame after tests"""
    pygame.quit()
