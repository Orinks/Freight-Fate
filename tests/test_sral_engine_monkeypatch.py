import pytest
from src.sral_wrapper import SRALEngine, SRALEngines
from unittest.mock import MagicMock

def test_sral_engine_init(mock_sral_dll):
    """Test SRALEngine initialization with mocked DLL."""
    # Create SRALEngine with mocked DLL
    engine = SRALEngine()
    
    # Verify that the DLL was loaded and initialized
    mock_sral_dll.SRAL_Initialize.assert_called_once()

def test_sral_engine_output(mock_sral_dll):
    """Test SRALEngine output method with mocked DLL."""
    # Create SRALEngine with mocked DLL
    engine = SRALEngine()
    
    # Test output method
    result = engine.output("Test message", interrupt=True)
    assert result is True
    mock_sral_dll.SRAL_Speak.assert_called_once()
    
    # Verify the arguments
    args, kwargs = mock_sral_dll.SRAL_Speak.call_args
    assert len(args) == 2
    assert args[0] == b"Test message"
    assert args[1] is True

def test_sral_engine_speak_alias(mock_sral_dll):
    """Test SRALEngine speak method (alias for output) with mocked DLL."""
    # Create SRALEngine with mocked DLL
    engine = SRALEngine()
    
    # Test speak method (alias for output)
    result = engine.speak("Test message", interrupt=True)
    assert result is True
    mock_sral_dll.SRAL_Speak.assert_called_once()

def test_sral_engine_stop(mock_sral_dll):
    """Test SRALEngine stop method with mocked DLL."""
    # Create SRALEngine with mocked DLL
    engine = SRALEngine()
    
    # Test stop method
    result = engine.stop()
    assert result is True
    mock_sral_dll.SRAL_StopSpeech.assert_called_once()

def test_sral_engine_set_voice_by_index(mock_sral_dll):
    """Test SRALEngine set_voice_by_index method with mocked DLL."""
    # Create SRALEngine with mocked DLL
    engine = SRALEngine()
    
    # Test set_voice_by_index method
    result = engine.set_voice_by_index(1)
    assert result is True
    mock_sral_dll.SRAL_SetVoice.assert_called_once_with(1)

def test_sral_engine_get_available_voices(mock_sral_dll):
    """Test SRALEngine get_available_voices method with mocked DLL."""
    # Set up mock to return voice names
    mock_sral_dll.SRAL_GetVoiceCount.return_value = 2
    mock_sral_dll.SRAL_GetVoiceName.side_effect = [b"Voice 1", b"Voice 2"]
    
    # Create SRALEngine with mocked DLL
    engine = SRALEngine()
    
    # Test get_available_voices method
    voices = engine.get_available_voices()
    assert len(voices) == 2
    assert voices == ["Voice 1", "Voice 2"]
    mock_sral_dll.SRAL_GetVoiceCount.assert_called_once()
    assert mock_sral_dll.SRAL_GetVoiceName.call_count == 2

def test_sral_engine_set_voice_by_name(mock_sral_dll):
    """Test SRALEngine set_voice_by_name method with mocked DLL."""
    # Set up mock to return voice names
    mock_sral_dll.SRAL_GetVoiceCount.return_value = 2
    mock_sral_dll.SRAL_GetVoiceName.side_effect = [b"Voice 1", b"Voice 2"]
    
    # Create SRALEngine with mocked DLL
    engine = SRALEngine()
    
    # Test set_voice_by_name method
    result = engine.set_voice_by_name("Voice 2")
    assert result is True
    mock_sral_dll.SRAL_SetVoice.assert_called_once_with(1)  # Index 1 for "Voice 2"
    
    # Test with non-existent voice
    with pytest.raises(ValueError):
        engine.set_voice_by_name("Non-existent Voice")

def test_sral_engine_set_rate(mock_sral_dll):
    """Test SRALEngine set_rate method with mocked DLL."""
    # Create SRALEngine with mocked DLL
    engine = SRALEngine()
    
    # Test set_rate method
    result = engine.set_rate(75)
    assert result is True
    mock_sral_dll.SRAL_SetRate.assert_called_once_with(75)
    
    # Test invalid rate values
    with pytest.raises(ValueError):
        engine.set_rate(-10)
    
    with pytest.raises(ValueError):
        engine.set_rate(110)

def test_sral_engine_set_volume(mock_sral_dll):
    """Test SRALEngine set_volume method with mocked DLL."""
    # Create SRALEngine with mocked DLL
    engine = SRALEngine()
    
    # Test set_volume method
    result = engine.set_volume(60)
    assert result is True
    mock_sral_dll.SRAL_SetVolume.assert_called_once_with(60)
    
    # Test invalid volume values
    with pytest.raises(ValueError):
        engine.set_volume(-10)
    
    with pytest.raises(ValueError):
        engine.set_volume(110)

def test_sral_engine_get_volume(mock_sral_dll):
    """Test SRALEngine get_volume method with mocked DLL."""
    # Create SRALEngine with mocked DLL
    engine = SRALEngine()
    
    # Test get_volume method
    volume = engine.get_volume()
    assert volume == 75
    mock_sral_dll.SRAL_GetVolume.assert_called_once()

def test_sral_engine_set_pitch(mock_sral_dll):
    """Test SRALEngine set_pitch method with mocked DLL."""
    # Create SRALEngine with mocked DLL
    engine = SRALEngine()
    
    # Test set_pitch method
    result = engine.set_pitch(50)
    assert result is True
    mock_sral_dll.SRAL_SetEngineParameter.assert_called_once()
    
    # Test invalid pitch values
    with pytest.raises(ValueError):
        engine.set_pitch(-10)
    
    with pytest.raises(ValueError):
        engine.set_pitch(110)

def test_sral_engine_configure_voice(mock_sral_dll):
    """Test SRALEngine configure_voice method with mocked DLL."""
    # Set up mock to return voice names
    mock_sral_dll.SRAL_GetVoiceCount.return_value = 2
    mock_sral_dll.SRAL_GetVoiceName.side_effect = [b"Voice 1", b"Voice 2"]
    
    # Create SRALEngine with mocked DLL
    engine = SRALEngine()
    
    # Test configure_voice method with all parameters
    result = engine.configure_voice(
        voice_name="Voice 2",
        rate=60,
        volume=70,
        pitch=80
    )
    assert result is True
    
    # Verify that all the appropriate methods were called
    mock_sral_dll.SRAL_SetVoice.assert_called_once()
    mock_sral_dll.SRAL_SetRate.assert_called_once_with(60)
    mock_sral_dll.SRAL_SetVolume.assert_called_once_with(70)
    mock_sral_dll.SRAL_SetEngineParameter.assert_called_once()
