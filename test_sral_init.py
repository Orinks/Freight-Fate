from src.sral_tts import SRALEngine

def main():
	try:
		print("Initializing SRAL with SAPI mode...")
		sral = SRALEngine(speech_engine_mode="sapi")
		print("SRAL initialized successfully")
		
		print("Testing speech...")
		sral.output("SRAL initialization test successful")
		
	except Exception as e:
		print(f"Error occurred: {str(e)}")
		import traceback
		traceback.print_exc()

if __name__ == "__main__":
	main()
