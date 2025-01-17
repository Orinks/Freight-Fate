"""Test script for text-to-speech system."""
import os
import sys
import pytest
import time

# Add the src directory to the Python path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'src'))

from sral_tts import SRALEngine
from game.settings import Settings

class MockTTSEngine(SRALEngine):
    def __init__(self, speech_engine_mode="sapi"):
        self.outputs = []
        self.current_rate = 50
        self.current_pitch = 50
        self.current_voice = None
        self.is_speaking = False
        
    def output(self, text):
        self.outputs.append(text)
        self.is_speaking = True
        return True
        
    def stop(self):
        self.is_speaking = False
        return True
        
    def set_rate(self, rate):
        self.current_rate = rate
        return True
        
    def set_pitch(self, pitch):
        self.current_pitch = pitch
        return True
        
    def set_voice_by_name(self, voice):
        self.current_voice = voice
        return True
        
    def get_available_voices(self):
        return ["Voice1", "Voice2", "Voice3"]

def test_basic_speech():
    """Test basic text-to-speech functionality."""
    settings = Settings()
    tts_engine = MockTTSEngine(speech_engine_mode=settings.speech_engine_mode)
    
    test_phrases = [
        "Welcome to Freight Fate",
        "Testing text to speech functionality",
        "This is a longer sentence to test how the engine handles extended speech.",
        "Numbers test: 1, 2, 3, 4, 5",
        "Special characters: !, @, #, $, %"
    ]
    
    for phrase in test_phrases:
        assert tts_engine.output(phrase), f"Failed to speak: {phrase}"
        assert phrase in tts_engine.outputs, f"Phrase not found in outputs: {phrase}"

def test_speech_settings():
    """Test different speech settings."""
    settings = Settings()
    tts_engine = MockTTSEngine(speech_engine_mode="sapi")
    
    test_phrase = "This is a test of speech settings."
    
    # Test speech rates
    rates = [25, 50, 75]  # Slow, Normal, Fast
    for rate in rates:
        assert tts_engine.set_rate(rate), f"Failed to set rate: {rate}"
        assert tts_engine.current_rate == rate, f"Rate not set correctly: {rate}"
        assert tts_engine.output(test_phrase), "Failed to speak with new rate"
    
    # Test speech pitches
    pitches = [25, 50, 75]  # Low, Normal, High
    for pitch in pitches:
        assert tts_engine.set_pitch(pitch), f"Failed to set pitch: {pitch}"
        assert tts_engine.current_pitch == pitch, f"Pitch not set correctly: {pitch}"
        assert tts_engine.output(test_phrase), "Failed to speak with new pitch"
    
    # Test available voices
    voices = tts_engine.get_available_voices()
    assert len(voices) > 0, "No voices available"
    for voice in voices:
        assert tts_engine.set_voice_by_name(voice), f"Failed to set voice: {voice}"
        assert tts_engine.current_voice == voice, f"Voice not set correctly: {voice}"
        assert tts_engine.output(f"This is the {voice} voice."), "Failed to speak with new voice"

def test_interrupt_behavior():
    """Test speech interruption behavior."""
    settings = Settings()
    tts_engine = MockTTSEngine(speech_engine_mode=settings.speech_engine_mode)
    
    # Start long speech
    long_text = "This is a very long sentence that will take some time to speak. " * 3
    assert tts_engine.output(long_text), "Failed to start long speech"
    
    # Interrupt with new speech
    assert tts_engine.output("Interruption test!"), "Failed to interrupt speech"
    assert "Interruption test!" in tts_engine.outputs, "Interruption not found in outputs"
    
    # Test rapid successive speech
    for i in range(5):
        message = f"Quick message number {i + 1}"
        assert tts_engine.output(message), f"Failed to speak: {message}"
        assert message in tts_engine.outputs, f"Message not found in outputs: {message}"

def test_error_handling():
    """Test TTS error handling."""
    settings = Settings()
    tts_engine = MockTTSEngine(speech_engine_mode=settings.speech_engine_mode)
    
    # Test empty string
    assert tts_engine.output(""), "Failed to handle empty string"
    
    # Test None value
    with pytest.raises(Exception):
        tts_engine.output(None)
    
    # Test very long text
    long_text = "Test " * 1000
    assert tts_engine.output(long_text), "Failed to handle very long text"
    
    # Test special characters
    special_chars = "!@#$%^&*()_+{}|:<>?~`"
    assert tts_engine.output(special_chars), "Failed to handle special characters"
    
    # Test invalid voice
    assert not tts_engine.set_voice_by_name("NonexistentVoice"), "Should fail with invalid voice"
    
    # Test invalid rate
    with pytest.raises(Exception):
        tts_engine.set_rate(-1)
    with pytest.raises(Exception):
        tts_engine.set_rate(1000)
