import os
import sys
import time
from src.sral_wrapper import SRALWrapper, SRALEngines

def main():
	try:
		print("Initializing SRAL with SAPI only...")
		sral = SRALWrapper()
		engines_exclude = ~SRALEngines.SAPI
		sral.initialize(engines_exclude)
		
		# Test different speech rates using SAPI XML tags
		test_messages = [
			"<rate speed='-5'>This is very slow speech using SAPI rate control.</rate>",
			"<rate speed='0'>This is normal speed speech.</rate>",
			"<rate speed='5'>This is very fast speech using SAPI rate control.</rate>",
			# Test combination of rate and punctuation
			"<rate speed='3'>This. Is. Fast. Speech. With. Punctuation!</rate>"
		]
		
		for msg in test_messages:
			print(f"\nSpeaking: {msg}")
			sral.speak(msg, interrupt=True)
			time.sleep(4)  # Wait for speech to complete
		
		print("Speech rate test completed")
		
	except Exception as e:
		print(f"Error occurred: {str(e)}")
		import traceback
		traceback.print_exc()

if __name__ == "__main__":
	main()

