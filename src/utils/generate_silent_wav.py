import wave
import struct

def create_silent_wav(filename, duration=1.0, sample_rate=44100):
	"""Create a silent WAV file."""
	n_channels = 2
	sample_width = 2  # 2 bytes for 16-bit audio
	n_frames = int(duration * sample_rate)
	
	with wave.open(filename, 'wb') as wav_file:
		wav_file.setnchannels(n_channels)
		wav_file.setsampwidth(sample_width)
		wav_file.setframerate(sample_rate)
		
		# Generate silent frames (all zeros)
		silent_frame = struct.pack('h', 0) * n_channels
		for _ in range(n_frames):
			wav_file.writeframes(silent_frame)

if __name__ == "__main__":
	import os
	
	# Create directories if they don't exist
	dirs = [
		"assets/sounds/engine",
		"assets/sounds/vehicle",
		"assets/sounds/weather"
	]
	
	base_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
	for dir_path in dirs:
		full_path = os.path.join(base_dir, dir_path)
		os.makedirs(full_path, exist_ok=True)
	
	# List of files to create
	files = [
		# Engine sounds
		"engine/low.wav",
		"engine/mid.wav",
		"engine/high.wav",
		"engine/start.wav",
		"engine/rev.wav",
		# Vehicle sounds
		"vehicle/gear_shift.wav",
		"vehicle/brake.wav",
		"vehicle/tire_screech.wav",
		"vehicle/collision.wav",
		# Weather sounds
		"weather/rain_light.wav",
		"weather/rain_heavy.wav",
		"weather/thunder.wav",
		"weather/wind.wav"
	]
	
	# Create each silent WAV file
	for file in files:
		full_path = os.path.join(base_dir, "assets/sounds", file)
		create_silent_wav(full_path)
		print(f"Created {file}")