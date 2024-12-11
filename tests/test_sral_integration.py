from src.sral_tts import SRALEngine
import time

def test_sral():
    print("Testing SRAL integration...")
    
    # Initialize engine
    try:
        engine = SRALEngine()
        print("[PASS] SRAL initialized successfully")
    except Exception as e:
        print(f"[FAIL] Failed to initialize SRAL: {e}")
        return
    
    # Test basic speech
    try:
        engine.output("Testing SRAL integration.")
        time.sleep(2)  # Wait for speech to complete
        print("[PASS] Basic speech test passed")
    except Exception as e:
        print(f"[FAIL] Basic speech test failed: {e}")
    
    # Test interruption
    try:
        engine.output("This is a long sentence that should be interrupted.", interrupt=False)
        time.sleep(0.5)  # Let it start speaking
        engine.output("Interruption test.", interrupt=True)
        time.sleep(1)
        print("[PASS] Interruption test passed")
    except Exception as e:
        print(f"[FAIL] Interruption test failed: {e}")
    
    # Test stop
    try:
        engine.output("This speech should be stopped.", interrupt=False)
        time.sleep(0.5)  # Let it start speaking
        engine.stop()
        print("[PASS] Stop test passed")
    except Exception as e:
        print(f"[FAIL] Stop test failed: {e}")

if __name__ == "__main__":
    test_sral()
