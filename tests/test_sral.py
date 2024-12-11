from src.sral_wrapper import SRALWrapper, SRALEngines

def test_sral():
    try:
        # Initialize SRAL
        sral = SRALWrapper()
        
        # Print current engine
        engine_id = sral.get_current_engine()
        print(f"Current engine ID: {engine_id}")
        
        # Test basic speech
        print("Testing speech...")
        result = sral.speak("This is a test of the SRAL speech system.")
        print(f"Speech result: {result}")
        
        # Test stop/pause/resume
        print("\nTesting speech controls...")
        sral.speak("This is a longer message that we will try to control.", interrupt=True)
        input("Press Enter to pause...")
        sral.pause()
        
        input("Press Enter to resume...")
        sral.resume()
        
        input("Press Enter to stop...")
        sral.stop()
        
    except Exception as e:
        print(f"Error occurred: {e}")

if __name__ == "__main__":
    test_sral()
