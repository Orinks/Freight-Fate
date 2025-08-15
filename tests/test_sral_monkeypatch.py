import pytest
from src.sral_wrapper import SRALWrapper, SRALEngines
from unittest.mock import MagicMock

def test_sral_wrapper_init(mock_sral_dll):
    """Test SRALWrapper initialization with mocked DLL."""
    # Create SRAL wrapper with mocked DLL
    sral = SRALWrapper()
    
    # Verify that the DLL was loaded and initialized
    mock_sral_dll.SRAL_Initialize.assert_called_once()
    
    # Test getting current engine
    engine_id = sral.get_current_engine()
    assert engine_id == 4  # SRALEngines.SAPI
    mock_sral_dll.SRAL_GetCurrentEngine.assert_called_once()

def test_sral_wrapper_speak(mock_sral_dll):
    """Test SRALWrapper speak method with mocked DLL."""
    # Create SRAL wrapper with mocked DLL
    sral = SRALWrapper()
    
    # Test speak method
    result = sral.speak("Test message", interrupt=True)
    assert result is True
    mock_sral_dll.SRAL_Speak.assert_called_once()
    
    # Verify the arguments
    args, kwargs = mock_sral_dll.SRAL_Speak.call_args
    assert len(args) == 2
    assert args[0] == b"Test message"
    assert args[1] is True

def test_sral_wrapper_stop(mock_sral_dll):
    """Test SRALWrapper stop method with mocked DLL."""
    # Create SRAL wrapper with mocked DLL
    sral = SRALWrapper()
    
    # Test stop method
    result = sral.stop()
    assert result is True
    mock_sral_dll.SRAL_StopSpeech.assert_called_once()

def test_sral_wrapper_pause_resume(mock_sral_dll):
    """Test SRALWrapper pause and resume methods with mocked DLL."""
    # Create SRAL wrapper with mocked DLL
    sral = SRALWrapper()
    
    # Test pause method
    result = sral.pause()
    assert result is True
    mock_sral_dll.SRAL_PauseSpeech.assert_called_once()
    
    # Test resume method
    result = sral.resume()
    assert result is True
    mock_sral_dll.SRAL_ResumeSpeech.assert_called_once()

def test_sral_wrapper_volume_control(mock_sral_dll):
    """Test SRALWrapper volume control methods with mocked DLL."""
    # Create SRAL wrapper with mocked DLL
    sral = SRALWrapper()
    
    # Test setting volume
    assert sral.set_volume(75), "Failed to set volume to 75%"
    mock_sral_dll.SRAL_SetVolume.assert_called_once_with(75)
    
    # Test getting volume
    volume = sral.get_volume()
    assert volume == 75, f"Volume should be 75%, got {volume}%"
    mock_sral_dll.SRAL_GetVolume.assert_called_once()
    
    # Test invalid volume values
    with pytest.raises(ValueError):
        sral.set_volume(-10)
    
    with pytest.raises(ValueError):
        sral.set_volume(110)

def test_sral_wrapper_rate_control(mock_sral_dll):
    """Test SRALWrapper rate control methods with mocked DLL."""
    # Create SRAL wrapper with mocked DLL
    sral = SRALWrapper()
    
    # Test setting rate
    assert sral.set_rate(50), "Failed to set rate to 50%"
    mock_sral_dll.SRAL_SetRate.assert_called_once_with(50)
    
    # Test getting rate
    rate = sral.get_rate()
    assert rate == 50, f"Rate should be 50%, got {rate}%"
    mock_sral_dll.SRAL_GetRate.assert_called_once()
    
    # Test invalid rate values
    with pytest.raises(ValueError):
        sral.set_rate(-10)
    
    with pytest.raises(ValueError):
        sral.set_rate(110)
