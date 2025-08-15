import pytest
from unittest.mock import MagicMock, patch

# We import SRALWrapper after patching ctypes.CDLL so the wrapper uses our mock

def make_mock_sral():
    mock = MagicMock()
    mock.SRAL_Initialize.return_value = True
    mock.SRAL_Speak.return_value = True
    mock.SRAL_StopSpeech.return_value = True
    mock.SRAL_PauseSpeech.return_value = True
    mock.SRAL_ResumeSpeech.return_value = True
    mock.SRAL_GetCurrentEngine.return_value = 4
    mock.SRAL_SetRate.return_value = True
    mock.SRAL_GetRate.return_value = 50
    mock.SRAL_SetVolume.return_value = True
    mock.SRAL_GetVolume.return_value = 75
    return mock

@patch('ctypes.CDLL')
def test_sral_wrapper_core_functions(mock_cdll):
    mock_cdll.return_value = make_mock_sral()
    from src.sral_wrapper import SRALWrapper

    sral = SRALWrapper()

    # init + engine id
    assert sral.get_current_engine() == 4

    # speak/stop/pause/resume
    assert sral.speak("Test", interrupt=True) is True
    assert sral.pause() is True
    assert sral.resume() is True
    assert sral.stop() is True

    # rate
    assert sral.set_rate(50) is True
    assert sral.get_rate() == 50

    # volume and validation
    assert sral.set_volume(75) is True
    assert sral.get_volume() == 75
    with pytest.raises(ValueError):
        sral.set_volume(-1)
    with pytest.raises(ValueError):
        sral.set_volume(101)
