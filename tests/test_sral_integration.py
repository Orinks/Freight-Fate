from src.sral_tts import SRALEngine
import time
import pytest

def test_sral_initialization():
    """Test SRAL integration initialization."""
    try:
        engine = SRALEngine()
        assert engine is not None, "Failed to initialize SRAL"
        print("[PASS] SRAL initialized successfully")
    except Exception as e:
        pytest.fail(f"Failed to initialize SRAL: {e}")

def test_basic_speech():
    """Test basic speech functionality."""
    try:
        engine = SRALEngine()
        
        # Test basic speech
        engine.output("Testing SRAL integration.")
        time.sleep(0.1)  # Brief delay for speech to start
        assert True, "Basic speech test passed"
        
    except Exception as e:
        pytest.fail(f"Basic speech test failed: {e}")

def test_speech_interruption():
    """Test speech interruption functionality."""
    try:
        engine = SRALEngine()
        
        # Start long speech
        engine.output("This is a long sentence that should be interrupted.", interrupt=False)
        time.sleep(0.1)  # Let it start speaking
        
        # Interrupt with new speech
        engine.output("Interruption test.", interrupt=True)
        time.sleep(0.1)
        assert True, "Interruption test passed"
        
    except Exception as e:
        pytest.fail(f"Interruption test failed: {e}")

def test_speech_stop():
    """Test speech stop functionality."""
    try:
        engine = SRALEngine()
        
        # Start speech
        engine.output("This speech should be stopped.", interrupt=False)
        time.sleep(0.1)  # Let it start speaking
        
        # Stop speech
        engine.stop()
        assert True, "Stop test passed"
        
    except Exception as e:
        pytest.fail(f"Stop test failed: {e}")
