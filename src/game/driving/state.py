import pygame
from .vehicle import EngineDef, TruckSpecs, TruckPhysics
from .transmission import Transmission
from .input_handler import DrivingInputHandler
from .hud import DrivingHUD
from .audio_hud import AudioHUD
from ..tutorial_objectives import TutorialManager
from ..pause_menu import PauseMenu

class DrivingState:
    def __init__(self, screen, tts_engine, sound_manager, settings, start_city, start_location):
        """Initialize the driving state."""
        self.screen = screen
        self.tts_engine = tts_engine
        self.sound_manager = sound_manager
        self.settings = settings
        self.city = start_city
        self.location = start_location
        
        # Obstacle tracking
        self.obstacles = []
        
        # Announce starting location
        if self.tts_engine:
            self.tts_engine.output(f"Starting at {self.location['name']} in {self.city}")
        
        # Initialize truck components
        engine = EngineDef(
            max_hp=800.0,
            max_torque=3000.0,
            rpm_range=(600, 2500),
            optimal_rpm=1500,
            gear_ratios=[3.5, 2.8, 2.2, 1.8, 1.5, 1.2, 1.0]  # 1st through 7th gears
        )
        specs = TruckSpecs(
            mass=8000.0,
            drag_coefficient=0.5,
            rolling_resistance=0.01,
            wheel_radius=0.5,
            brake_force=40000.0,
            engine=engine
        )
        self.truck = TruckPhysics(specs)
        self.truck.sound_manager = self.sound_manager  # Give truck access to sound manager
        self.transmission = Transmission(gear_ratios=engine.gear_ratios)
        self.transmission.sound_manager = self.sound_manager  # Give transmission access to sound manager
        
        # Initialize HUD components with settings
        self.hud = DrivingHUD(self.screen, self.truck, self.transmission, self.settings)
        self.audio_hud = AudioHUD(self.tts_engine, self.truck, self.transmission, self.settings)
        self.audio_hud.speak(f"Starting at {self.location['name']} in {self.city}")
        
        # Initialize input handler
        self.input_handler = DrivingInputHandler(self.truck, self.transmission)
        self.input_handler.truck = self.truck  # Give input handler access to truck for sound effects
        self.input_handler.set_settings(self.settings)
        
        # Start engine sounds
        self.sound_manager.play_engine_start()
        self.sound_manager.play_engine_idle()
        
        # Game state
        self.paused = False
        self.pause_menu = PauseMenu(self.screen, self.tts_engine, self.sound_manager)
        
        # Initialize map view
        self.map_view = None  # Will be initialized when needed
        
        # Add tutorial manager
        self.tutorial_manager = TutorialManager(screen, tts_engine, {
            'visited_location_types': [],
            'distance_driven': 0.0,
            'accidents': 0,
            'violations': 0
        })
        
        # Tutorial state tracking
        self.controls_explained = False
        self.engine_started = False
        self.practice_complete = False
        self.safe_driving_start_pos = None
        self.last_accident_pos = None
        
        # Trigger first tutorial objective
        self.tutorial_manager.update_objective("controls_learned")
        
        # Camera and environment setup
        self.camera_x = 0
        self.camera_y = 0
        self.environment_width = 2000
        self.environment_height = 1000
        
        # Define environment elements based on location type
        self.buildings = []
        self.roads = []
        self.setup_environment()
        self.update_obstacles()
        
    def setup_environment(self):
        """Setup the environment based on location type."""
        location_type = self.location['type'].lower()
        
        # Base road
        self.roads.append(pygame.Rect(0, 400, self.environment_width, 200))
        
        # Add buildings based on location type
        if 'warehouse' in location_type:
            self.buildings.extend([
                pygame.Rect(100, 100, 300, 200),  # Main warehouse
                pygame.Rect(500, 100, 150, 100),  # Office building
                pygame.Rect(100, 700, 200, 150),  # Storage building
            ])
        elif 'terminal' in location_type:
            self.buildings.extend([
                pygame.Rect(100, 100, 400, 300),  # Terminal building
                pygame.Rect(600, 100, 200, 200),  # Control tower
                pygame.Rect(100, 700, 300, 200),  # Loading docks
            ])
        elif 'distribution' in location_type:
            self.buildings.extend([
                pygame.Rect(100, 100, 500, 200),  # Distribution center
                pygame.Rect(700, 100, 200, 200),  # Storage facility
                pygame.Rect(100, 700, 400, 200),  # Loading area
            ])
        
    def handle_input(self, event):
        """Handle input events."""
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                if self.paused:
                    self.paused = False
                    if self.tts_engine:
                        self.tts_engine.output("Game resumed")
                else:
                    self.paused = True
                    if self.tts_engine:
                        self.tts_engine.output("Game paused")
                return None
            elif event.key == pygame.K_m:
                if not self.map_view:
                    from ..map_view import MapView
                    self.map_view = MapView(self.screen, self.tts_engine, self.cities_data)
                return None
            # Tutorial-specific input handling
            elif event.key == pygame.K_e and not self.engine_started:
                self.engine_started = True
                self.tutorial_manager.update_objective("engine_started")
            elif event.key == pygame.K_h:
                current_obj = self.tutorial_manager.objectives[self.tutorial_manager.current_objective_index]
                if self.tts_engine and current_obj.help_text:
                    self.tts_engine.output(current_obj.help_text)

        # Handle pause menu input when paused
        if self.paused:
            result = self.pause_menu.handle_input(event)
            if result == "resume":
                self.paused = False
                if self.tts_engine:
                    self.tts_engine.output("Game resumed")
            return result
                
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

    def update_obstacles(self):
        """Convert buildings and other elements to obstacle rectangles."""
        self.obstacles = []
        # Add buildings as obstacles
        for building in self.buildings:
            self.obstacles.append(building)
            
    def update(self, dt):
        """Update game state."""
        if not self.paused:
            # Update input handler first
            self.input_handler.update(dt)
            
            # Tutorial objective tracking
            self._update_tutorial_objectives(dt)
            
            # Transfer input handler state to truck
            self.truck.throttle = self.input_handler.throttle_input
            self.truck.brake = self.input_handler.brake_input
            self.truck.clutch = self.input_handler.clutch_input
            
            # Debug input state
            print(f"\rInput state - Throttle: {self.input_handler.throttle_input:.2f} | "
                  f"Brake: {self.input_handler.brake_input:.2f} | "
                  f"Clutch: {self.input_handler.clutch_input:.2f}", end='')
            
            # Update vehicle physics with obstacles
            self.truck.update(dt, self.obstacles)
            
            # Check if collision occurred and handle it
            if self.truck.check_collision(self.obstacles):
                self.handle_collision()
            
            # Update transmission with clutch state
            self.transmission.update(dt, self.input_handler.clutch_input)
            
            # Update audio feedback
            self.audio_hud.update(dt)
            
            # Update engine sound based on RPM
            self.sound_manager.update_engine_sound(self.truck.engine_rpm, self.truck.specs.engine.rpm_range[1])
            
            # Update camera to follow truck
            self.camera_x = self.truck.position - (self.screen.get_width() / 2)
            self.camera_y = 0  # Keep vertical position fixed for side view
            
            # Debug output
            print(f"\rSpeed: {self.truck.speed:.1f} km/h | "
                  f"Throttle: {self.truck.throttle:.2f} | "
                  f"Position: {self.truck.position:.1f}m", end='')
        
    def render(self):
        """Render the current frame."""
        if self.map_view:
            self.map_view.render()
        else:
            # Clear screen with sky color
            self.screen.fill((135, 206, 235))  # Sky blue
            
            # Draw environment
            self.render_environment()
            
            # Draw HUD
            self.hud.render()
            
            # Draw pause menu if paused
            if self.paused:
                self.pause_menu.render()
            
            # Render tutorial if active
            if self.tutorial_manager:
                self.tutorial_manager.render()
            
            # Update display
            pygame.display.flip()
        
    def _update_tutorial_objectives(self, dt):
        """Track and update tutorial objectives."""
        if not self.tutorial_manager.show_tutorial:
            return
            
        current_obj = self.tutorial_manager.objectives[self.tutorial_manager.current_objective_index]
        
        # Track practice driving completion
        if current_obj.title == "Practice Driving" and not self.practice_complete:
            if self.truck.speed > 5.0 and self.input_handler.brake_input > 0.5:
                self.practice_complete = True
                self.tutorial_manager.update_objective("practice_complete")
        
        # Track safe driving progress
        if current_obj.title == "Safe Driving":
            if self.safe_driving_start_pos is None:
                self.safe_driving_start_pos = self.truck.position
            
            distance_driven = abs(self.truck.position - self.safe_driving_start_pos)
            if distance_driven >= 1609:  # 1 mile in meters
                if not self.last_accident_pos or (self.truck.position - self.last_accident_pos) >= 1609:
                    self.tutorial_manager.update_objective("safe_mile")
        
        # Update distance driven
        self.tutorial_manager.player_data['distance_driven'] += abs(self.truck.speed * dt)
        
    def handle_collision(self):
        """Handle collision events."""
        self.tutorial_manager.player_data['accidents'] += 1
        self.last_accident_pos = self.truck.position
        if self.tts_engine:
            self.tts_engine.output("Collision detected! Drive more carefully.")
            
    def handle_traffic_violation(self):
        """Handle traffic violation events."""
        self.tutorial_manager.player_data['violations'] += 1
        if self.tts_engine:
            self.tts_engine.output("Traffic violation detected! Follow the rules of the road.")

    def render_environment(self):
        """Draw the environment, buildings, and roads relative to camera."""
        # Draw ground
        ground_rect = pygame.Rect(0, 500, self.screen.get_width(), self.screen.get_height() - 500)
        pygame.draw.rect(self.screen, (34, 139, 34), ground_rect)  # Forest green
        
        # Draw roads (shifted by camera)
        for road in self.roads:
            screen_rect = pygame.Rect(
                road.x - self.camera_x,
                road.y,
                road.width,
                road.height
            )
            pygame.draw.rect(self.screen, (128, 128, 128), screen_rect)  # Gray
            
            # Draw road markings
            center_y = road.y + (road.height / 2)
            marking_length = 50
            marking_gap = 50
            start_x = road.x - (self.camera_x % (marking_length + marking_gap))
            while start_x < self.screen.get_width():
                pygame.draw.line(self.screen, (255, 255, 255),
                               (start_x, center_y),
                               (start_x + marking_length, center_y), 3)
                start_x += marking_length + marking_gap
        
        # Draw buildings (shifted by camera)
        for building in self.buildings:
            screen_rect = pygame.Rect(
                building.x - self.camera_x,
                building.y,
                building.width,
                building.height
            )
            pygame.draw.rect(self.screen, (139, 69, 19), screen_rect)  # Brown
            # Add simple windows
            window_size = 20
            for x in range(int(building.width / window_size)):
                for y in range(int(building.height / window_size)):
                    window_rect = pygame.Rect(
                        screen_rect.x + (x * window_size) + 5,
                        screen_rect.y + (y * window_size) + 5,
                        window_size - 10,
                        window_size - 10
                    )
                    pygame.draw.rect(self.screen, (173, 216, 230), window_rect)  # Light blue
        
        # Draw truck
        truck_x = (self.screen.get_width() / 2) - 25  # Center of screen
        truck_y = 450  # Just above road
        truck_width = 50
        truck_height = 30
        
        # Truck body (cab)
        pygame.draw.rect(self.screen, (255, 0, 0),  # Red
                        (truck_x, truck_y, truck_width * 0.4, truck_height))
        # Truck trailer
        pygame.draw.rect(self.screen, (200, 200, 200),  # Gray
                        (truck_x + (truck_width * 0.4), truck_y,
                         truck_width * 0.6, truck_height))
        # Wheels
        wheel_radius = 5
        wheel_positions = [
            (truck_x + 10, truck_y + truck_height),  # Front wheels
            (truck_x + truck_width - 10, truck_y + truck_height)  # Back wheels
        ]
        for wx, wy in wheel_positions:
            pygame.draw.circle(self.screen, (0, 0, 0), (int(wx), int(wy)), wheel_radius)
