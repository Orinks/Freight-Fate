import pygame
from .vehicle import TruckPhysics, TruckSpecs, EngineDef
from .transmission import Transmission
from .input_handler import DrivingInputHandler
from .hud import DrivingHUD
from .audio_hud import AudioHUD
from ..settings import Settings
import os

class DrivingState:
    def __init__(self, screen, tts_engine, location_data, sound_manager, cities_data=None):
        """Initialize the driving state.
        
        Args:
            screen: Pygame display surface
            tts_engine: Text-to-speech engine
            location_data: Dictionary containing city and location information
            sound_manager: Sound manager instance
            cities_data: Dictionary containing all cities and their locations
        """
        self.tutorial_manager = None  # Will be set by FreightFate
        self.cities_data = cities_data
        print(f"Tutorial manager initialized: {self.tutorial_manager is not None}")
        print("\nDrivingState initialized. Tutorial manager will be set later.")
        self.screen = screen
        self.tts_engine = tts_engine
        self.city = location_data['city']
        self.location = location_data['location']
        self.sound_manager = sound_manager
        
        # Initialize settings
        self.settings = Settings()
        
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
            mass=8000.0,  # kg
            drag_coefficient=0.7,
            rolling_resistance=0.015,
            wheel_radius=0.5,
            brake_force=40000.0,
            engine=engine
        )
        self.truck = TruckPhysics(specs)
        self.transmission = Transmission(gear_ratios=engine.gear_ratios)
        
        # Initialize HUD components with settings
        self.hud = DrivingHUD(self.screen, self.truck, self.transmission, self.settings)
        self.audio_hud = AudioHUD(self.tts_engine, self.truck, self.transmission, self.settings)
        
        # Initialize input handler
        self.input_handler = DrivingInputHandler(self.truck, self.transmission)
        self.input_handler.set_settings(self.settings)
        
        # Start engine sound
        self.sound_manager.play_engine_idle()
        
        # Game state
        self.paused = False
        self.map_view = None  # Will be initialized when needed
        
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
            elif event.key == pygame.K_m:
                if not self.map_view:
                    from ..map_view import MapView
                    self.map_view = MapView(self.screen, self.tts_engine, self.cities_data)
                return None
                
        # Handle tutorial input first if tutorial is active
        if self.tutorial_manager:
            self.tutorial_manager.handle_event(event)
                
        # Handle audio HUD input next
        if self.audio_hud.handle_input(event):
            print("Audio HUD handled input")  # Debug output
            return None
                
        if not self.paused:
            # Handle driving input
            self.input_handler.handle_event(event)
        
        return None
        
    def update(self, dt):
        """Update game state.
        
        Args:
            dt: Time delta since last update in seconds
        """
        if not self.paused:
            # Update input handler first
            self.input_handler.update(dt)
            
            # Update vehicle physics
            self.truck.update(dt)
            
            # Update transmission with clutch state
            self.transmission.update(dt, self.input_handler.clutch_input)
            
            # Update audio feedback
            self.audio_hud.update(dt)
            
            # Update engine sound based on RPM
            self.sound_manager.update_engine_sound(self.truck.engine_rpm, self.truck.specs.engine.rpm_range[1])
        
    def render(self):
        """Render the current frame."""
        if self.map_view:
            self.map_view.render()
        else:
            # Clear screen
            self.screen.fill((100, 100, 100))  # Gray background for road
            
            # Draw HUD
            self.hud.render()
            
            # Render tutorial if active
            if self.tutorial_manager:
                self.tutorial_manager.render()
            
            # Update display
            pygame.display.flip()
