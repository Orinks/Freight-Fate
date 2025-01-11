import os
import sys
import ctypes

print("Current working directory:", os.getcwd())
print("\nChecking for SRAL.dll...")
dll_path = os.path.join(os.path.abspath("src"), "SRAL.dll")
print("Looking for DLL at:", dll_path)
print("DLL exists:", os.path.exists(dll_path))

try:
	print("\nAttempting to load SRAL.dll...")
	sral = ctypes.CDLL(dll_path)
	print("Successfully loaded SRAL.dll")
except Exception as e:
	print("Error loading SRAL.dll:", str(e))
	import traceback
	traceback.print_exc()