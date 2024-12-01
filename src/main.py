import os
import json
import pygame
import accessible_output3.outputs.auto
from game.menu import Menu
from game.route_selector import RouteSelector
from game.job_board import JobBoard
from game.objectives import ObjectiveGenerator, RouteProgress
from game.location_selector import LocationSelector
from game.tutorial_objectives import TutorialManager
from game.help_system import HelpSystem
from game.driving.vehicle import TruckPhysics, TruckSpecs, EngineDef
from game.driving.transmission import Transmission
from game.driving.input_handler import DrivingInputHandler
from game.driving.state import DrivingState
from game.weather.weather_manager import WeatherManager
from game.weather.forecast_ui import WeatherForecastUI
from game.sound_manager import SoundManager

print("Starting game initialization...")

os.environ['PYGAME_HIDE_SUPPORT_PROMPT'] = "hide"

print("All modules imported successfully")

class FreightFate:
    def __init__(self):
        """Initialize the game."""
        print("\n=== Game Initialization ===")
        print("1. Starting pygame initialization...")
        
        # Initialize Pygame
        pygame.init()
        print("- Pygame initialized:", pygame.get_init())
        
        # Initialize sound system
        print("\n2. Sound System Setup:")
        try:
            print("- Current mixer settings:", pygame.mixer.get_init())
            pygame.mixer.quit()  # Reset mixer
            print("- Mixer reset")
            
            pygame.mixer.pre_init(44100, -16, 2, 2048)
            print("- Mixer pre-initialized")
            
            pygame.mixer.init()
            print("- Mixer initialized with settings:", pygame.mixer.get_init())
            print("- Get busy:", pygame.mixer.get_busy())
            print("- Available channels:", pygame.mixer.get_num_channels())
            print("- Driver:", pygame.mixer.get_driver())
        except Exception as e:
            print(f"! Failed to initialize sound system: {e}")
        
        # Set up the display
        print("\n3. Display Setup:")
        self.screen = pygame.display.set_mode((800, 600))
        pygame.display.set_caption("Freight Fate")
        print("- Display initialized:", self.screen.get_size())
        
        # Initialize TTS
        print("\n4. TTS Setup:")
        self.tts_engine = accessible_output3.outputs.auto.Auto()
        print("- TTS engine initialized")
        
        # Initialize sound manager
        print("\n5. Sound Manager Setup:")
        self.sound_manager = SoundManager(volume=0.2)
        debug_info = self.sound_manager.get_debug_info()
        for key, value in debug_info.items():
            print(f"- {key}: {value}")
        
        # Load city data
        print("\n6. Loading Game Data:")
        current_file = os.path.abspath(__file__)
        project_root = os.path.dirname(os.path.dirname(current_file))
        cities_path = os.path.join(project_root, 'data', 'cities.json')
        try:
            with open(cities_path, 'r') as f:
                self.cities_data = json.load(f)
            print(f"- Cities data loaded from {cities_path}")
        except Exception as e:
            print(f"! Failed to load cities data: {e}")
            self.cities_data = None
            
        # Game states
        self.states = {
            'menu': Menu(self.screen, self.tts_engine, self.sound_manager, self.cities_data),
            'driving': None  # Will be initialized when needed
        }
        self.current_state = 'menu'
        print("\n=== Initialization Complete ===\n")
        
        # Start menu music
        self.sound_manager.play_menu_music()

    def run(self):
        """Main game loop."""
        running = True
        clock = pygame.time.Clock()
        while running:
            dt = clock.tick(60) / 1000.0  # Get time since last frame in seconds
            
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                    break
                    
                if self.current_state == 'menu':
                    result = self.states['menu'].handle_input(event)
                    if result == 'exit':
                        running = False
                        break
                    elif isinstance(result, tuple) and result[0] == 'start_game':
                        self.start_game(result[1])
                elif self.current_state == 'driving':
                    # Handle driving state input
                    print(f"Handling driving input for event: {event}")  # Debug output
                    result = self.states['driving'].handle_input(event)
                    if result == 'menu':
                        self.current_state = 'menu'
                        
            # Update driving state
            if self.current_state == 'driving':
                self.states['driving'].update(dt)
                
            # Render current state
            if self.current_state == 'menu':
                self.states['menu'].render()
            elif self.current_state == 'driving':
                self.states['driving'].render()
                
            pygame.display.flip()
            
        pygame.quit()

    def speak(self, text):
        if self.tts_engine:
            self.tts_engine.output(text)

    def handle_state_result(self, result):
        if not result:
            return
            
        if self.current_state == 'menu':
            if result == 'new_game':
                self.current_state = 'location_selector'
                self.states['location_selector'].set_city(self.player['current_city'])
                self.speak("Welcome to Freight Fate. Find a job location using arrow keys.")
                
        elif self.current_state == 'location_selector':
            if isinstance(result, dict):
                if result['action'] == 'visit_location':
                    self.player['current_location'] = result['location']
                    location_type = result['location']['type']
                    self.player['visited_location_types'].add(location_type)
                    
                    # Update tutorial objectives
                    reward = self.tutorial_manager.update_objective("visit_location")
                    if reward:
                        self.player['money'] += reward
                    
                    if len(self.player['visited_location_types']) >= 3:
                        reward = self.tutorial_manager.update_objective("visit_all_types")
                        if reward:
                            self.player['money'] += reward
                    
                    self.current_state = 'job_board'
                    self.states['job_board'].refresh_jobs(
                        self.player['current_city'],
                        self.player['level'],
                        self.player['current_location']
                    )
                    
        elif self.current_state == 'job_board':
            if result == "accept_job":
                # Update tutorial objective for accepting first job
                reward = self.tutorial_manager.update_objective("accept_job")
                if reward:
                    self.player['money'] += reward
                
                self.current_state = 'route_selection'
                current_job = self.states['job_board'].current_job
                self.states['route_selection'].set_destination(current_job.end_city)
                
        elif self.current_state == 'route_selection':
            if isinstance(result, dict) and 'highway' in result:
                self.current_highway = result['highway']
                self.highway_conditions = result['conditions']
                self.speak(f"Starting journey on {self.current_highway}. "
                         f"Traffic is {self.highway_conditions['traffic']}. "
                         f"Terrain is {self.highway_conditions['terrain']}.")
                self.current_state = 'driving'

    def render(self):
        """Render the current game state."""
        # Clear screen
        self.screen.fill((0, 0, 0))
        
        # Render current state
        self.states[self.current_state].render()
        
        # Render driving-specific elements
        if self.current_state == 'driving':
            # Render weather effects
            self.weather_manager.render(self.screen)
            
            # Render weather UI
            self.weather_ui.render(self.screen, (10, 10))
            
            # Render tutorial objectives if active
            self.tutorial_manager.render()
        
        # Render help system if visible
        self.help_system.render()
        
        pygame.display.flip()

    def start_game(self, location):
        # Stop menu music
        self.sound_manager.stop_menu_music()
        
        # Initialize driving state with selected location
        self.states['driving'] = DrivingState(self.screen, self.tts_engine, location, self.sound_manager)
        self.current_state = 'driving'

if __name__ == "__main__":
    print("Creating game instance...")
    game = FreightFate()
    print("Starting game loop...")
    game.run()
