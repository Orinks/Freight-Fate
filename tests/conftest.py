import pytest
import pygame
import warnings

# Suppress pygame welcome message
pygame.init()
warnings.filterwarnings("ignore", category=DeprecationWarning)

@pytest.fixture(scope="session")
def pygame_display():
    """Initialize pygame display for tests."""
    pygame.init()
    screen = pygame.display.set_mode((800, 600))
    yield screen
    pygame.quit()

@pytest.fixture(scope="function")
def mock_screen():
    """Create a mock screen for tests that don't need real display."""
    class MockScreen:
        def __init__(self):
            self.size = (800, 600)
            
        def get_width(self):
            return self.size[0]
            
        def get_height(self):
            return self.size[1]
    
    return MockScreen()

@pytest.fixture(scope="function")
def mock_tts_engine():
    """Create a mock TTS engine for tests."""
    class MockTTSEngine:
        def __init__(self):
            self.last_output = None
            self.outputs = []
            
        def output(self, text):
            self.last_output = text
            self.outputs.append(text)
            return True
            
        def stop(self):
            return True
    
    return MockTTSEngine()

@pytest.fixture(scope="function")
def mock_sound_manager():
    """Create a mock sound manager for tests."""
    class MockSoundManager:
        def __init__(self):
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
    
    return MockSoundManager()
