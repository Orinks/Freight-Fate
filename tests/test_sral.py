from src.sral_wrapper import SRALWrapper, SRALEngines
import pytest

def test_sral_basic():
    """Test basic SRAL initialization and speech."""
    try:
        # Initialize SRAL
        sral = SRALWrapper()
        
        # Get and verify current engine
        engine_id = sral.get_current_engine()
        assert engine_id > 0, "Failed to get valid engine ID"
        print(f"Current engine ID: {engine_id}")
        
        # Test basic speech
        result = sral.speak("This is a test of the SRAL speech system.")
        assert result, "Speech failed to initiate"
        
    except Exception as e:
        pytest.fail(f"Error occurred: {e}")

def test_sral_controls():
    """Test SRAL speech controls (stop/pause/resume)."""
    try:
        sral = SRALWrapper()
        
        # Test long message with controls
        result = sral.speak("This is a longer message that we will try to control.", interrupt=True)
        assert result, "Failed to start speech"
        
        # Test pause
        assert sral.pause(), "Failed to pause speech"
        
        # Small delay to let pause take effect
        import time
        time.sleep(0.1)
        
        # Test resume
        assert sral.resume(), "Failed to resume speech"
        
        time.sleep(0.1)
        
        # Test stop
        assert sral.stop(), "Failed to stop speech"
        
    except Exception as e:
        pytest.fail(f"Error occurred: {e}")

def test_sral_engine_selection():
    """Test SRAL engine selection and properties."""
    try:
        sral = SRALWrapper()
        
        # Get initial engine
        initial_engine = sral.get_current_engine()
        assert initial_engine > 0, "Failed to get initial engine"
        
        # Test engine properties
        engine_name = sral.get_engine_name()
        assert engine_name, "Failed to get engine name"
        
        # Verify we can speak with current engine
        assert sral.speak("Testing engine properties."), "Speech failed"
        
    except Exception as e:
        pytest.fail(f"Error occurred: {e}")
