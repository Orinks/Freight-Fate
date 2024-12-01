import pygame
from .vehicle import TruckPhysics, TruckSpecs, EngineDef
from .transmission import Transmission
from .input_handler import DrivingInputHandler
from .hud import DrivingHUD
from .audio_hud import AudioHUD
import os

class DrivingState:
    def __init__(self, screen, tts_engine, location_data, sound_manager):
        """Initialize the driving state.
        
        Args:
            screen: Pygame display surface
            tts_engine: Text-to-speech engine
            location_data: Dictionary containing city and location information
            sound_manager: Sound manager instance
        """
        self.screen = screen
        self.tts_engine = tts_engine
        self.city = location_data['city']
        self.location = location_data['location']
        self.sound_manager = sound_manager
        
        # Announce starting location
        if self.tts_engine:
            self.tts_engine.output(f"Starting at {self.location['name']} in {self.city}")
        
        # Initialize truck components
        engine = EngineDef(
            max_hp=400.0,
            max_torque=1800.0,
            rpm_range=(600, 2500),
            optimal_rpm=1500,
            gear_ratios=[0.0, 3.5, 2.8, 2.2, 1.8, 1.5, 1.2, 1.0]  # 0 is neutral, then 1st through 7th
        )
        specs = TruckSpecs(
            mass=8000.0,
            drag_coefficient=0.7,
            rolling_resistance=0.015,
            wheel_radius=0.5,
            brake_force=40000.0,
            engine=engine
        )
        self.truck = TruckPhysics(specs)
        self.transmission = Transmission(gear_ratios=engine.gear_ratios)
        
        # Initialize input handler
        self.input_handler = DrivingInputHandler(self.truck, self.transmission)
        
        # Initialize HUD components
        self.hud = DrivingHUD(screen, self.truck, self.transmission)
        self.audio_hud = AudioHUD(self.truck, self.transmission, self.tts_engine)
        
        # Start engine sound
        self.sound_manager.play_engine_idle()
        
        # Game state
        self.paused = False
        
    def handle_input(self, event):
        """Handle input events."""
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                return 'menu'  # Return to menu
            elif event.key == pygame.K_p:
                self.paused = not self.paused
                if self.paused:
                    self.audio_hud.speak("Game paused")
                else:
                    self.audio_hud.speak("Game resumed")
                
        # Handle audio HUD input first
        if self.audio_hud.handle_input(event):
            print("Audio HUD handled input")  # Debug output
            return None
                
        if not self.paused:
            # Handle driving input
            self.input_handler.handle_event(event)
        
        return None
        
    def update(self, dt):
        """Update game state."""
        if not self.paused:
            # Update input handler first
            self.input_handler.update(dt)
            
            # Update vehicle physics
            self.truck.update(dt)
            
            # Update transmission with clutch state
            self.transmission.update(dt, self.input_handler.clutch_input)
            
            # Update audio feedback
            self.audio_hud.update()
            
            # Update engine sound based on RPM
            self.sound_manager.update_engine_sound(self.truck.engine_rpm, self.truck.specs.engine.rpm_range[1])
        
    def render(self):
        """Render the current frame."""
        # Clear screen
        self.screen.fill((100, 100, 100))  # Gray background for road
        
        # Draw HUD
        self.hud.render()
        
        # Update display
        pygame.display.flip()
