import sys
import traceback
import os

def test_import(module_name):
	try:
		print(f"\nAttempting to import {module_name}...")
		__import__(module_name)
		print(f"Successfully imported {module_name}")
	except Exception as e:
		print(f"Error importing {module_name}:")
		print(f"Error type: {type(e).__name__}")
		print(f"Error message: {str(e)}")
		traceback.print_exc()
		print()

# Add the absolute path to sys.path
src_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'src')
print(f"Adding to sys.path: {src_path}")
sys.path.append(src_path)

# Print current sys.path for debugging
print("\nCurrent sys.path:")
for path in sys.path:
	print(path)

modules = ['sral_tts', 'game.menu', 'game.route_selector', 'game.job_board', 
		   'game.driving.state', 'game.weather.weather_manager']

for module in modules:
	test_import(module)