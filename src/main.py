import os
import json
import pygame
from sral_tts import SRALEngine
from game.menu import Menu
from game.route_selector import RouteSelector
from game.job_board import JobBoard
from game.driving.state import DrivingState
from game.weather.weather_manager import WeatherManager
from game.weather.forecast_ui import WeatherForecastUI
from game.sound_manager import SoundManager
from game.settings_menu import SettingsMenu
from game.settings import Settings
from game.tutorial_objectives import TutorialManager

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
        
        # Initialize settings first
        self.settings = Settings()

        # Initialize TTS with the saved speech engine mode
        print("\n4. TTS Setup:")
        self.speech_system_status = "active"  # Can be "active", "fallback", or "disabled"
        try:
            print("- Attempting to initialize TTS with mode:", self.settings.speech_engine_mode)
            self.tts_engine = SRALEngine(speech_engine_mode=self.settings.speech_engine_mode)
            if self.tts_engine.speech_engine_mode != self.settings.speech_engine_mode:
                print(f"- TTS initialized in fallback mode: {self.tts_engine.speech_engine_mode}")
                self.speech_system_status = "fallback"
            else:
                print(f"- TTS successfully initialized with mode: {self.settings.speech_engine_mode}")
        except Exception as e:
            print(f"Critical: Could not initialize TTS: {e}")
            print("- Speech system will be disabled")
            self.tts_engine = None
            self.speech_system_status = "disabled"

        
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
            'menu': Menu(
                self.screen,
                self.tts_engine,
                self.sound_manager,
                self.cities_data,
                self.speech_system_status
            ),
            'driving': None,  # Will be initialized when needed
            'settings': SettingsMenu(
                self.screen,
                self.tts_engine,
                self.settings,
                self.sound_manager,
                self.update_tts_engine
            ),
            'location_selector': None,  # Will be initialized when needed
            'job_board': None,  # Will be initialized when needed
            'route_selection': None  # Will be initialized when needed
        }

        self.current_state = 'menu'
        print("\n=== Initialization Complete ===\n")
        
        # Start menu music
        self.sound_manager.play_menu_music()

    def update_tts_engine(self, new_engine):
        """Update TTS engine across all game states when it changes."""
        self.tts_engine = new_engine
        
        # Update speech system status
        if new_engine is None:
            self.speech_system_status = "disabled"
        elif new_engine.speech_engine_mode != self.settings.speech_engine_mode:
            self.speech_system_status = "fallback"
        else:
            self.speech_system_status = "active"
            
        # Update TTS engine and status in all states that use it
        if 'menu' in self.states:
            self.states['menu'].tts_engine = new_engine
            self.states['menu'].speech_status = self.speech_system_status
        if 'driving' in self.states and self.states['driving']:
            self.states['driving'].tts_engine = new_engine

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
                    elif result == 'settings':
                        self.current_state = 'settings'
                        if self.tts_engine:
                            self.tts_engine.output("Settings Menu. Use arrow keys to navigate options, Enter to adjust settings, Tab for help.")
                elif self.current_state == 'settings':
                    result = self.states['settings'].handle_input(event)
                    if result == 'back':
                        self.current_state = 'menu'
                        if self.tts_engine:
                            self.tts_engine.output("Main Menu. Use arrow keys to navigate, Enter to select, Tab for help.")
                elif self.current_state == 'driving':
                    # Handle driving state input
                    print(f"Handling driving input for event: {event}")  # Debug output
                    result = self.states['driving'].handle_input(event)
                    if result == 'menu':
                        self.current_state = 'menu'
                        # Stop driving sounds and start menu music
                        self.sound_manager.stop_all()
                        self.sound_manager.play_menu_music()
                    elif result == 'settings':
                        self.current_state = 'settings'
                        if self.tts_engine:
                            self.tts_engine.output("Settings Menu. Use arrow keys to navigate options, Enter to adjust settings, Tab for help.")
                        
            # Update driving state
            if self.current_state == 'driving':
                self.states['driving'].update(dt)
                
            # Render current state
            if self.current_state == 'menu':
                self.states['menu'].render()
            elif self.current_state == 'settings':
                self.states['settings'].render()
            elif self.current_state == 'driving':
                self.states['driving'].render()
                
            pygame.display.flip()
            
        # Clean up before exit
        if self.sound_manager:
            self.sound_manager.stop_all()
        if self.tts_engine:
            self.tts_engine.stop()
        if self.settings.is_dirty:  # Only save if changed
            self.settings.save_settings()
        pygame.quit()

    def speak(self, text):
        if self.tts_engine:
            self.tts_engine.output(text)
            # self.tts_engine.runAndWait()

    def handle_state_result(self, result):
        if not result:
            return
            
        if self.current_state == 'menu':
            if result == 'new_game':
                self.current_state = 'location_selector'
                if 'location_selector' in self.states:
                    self.states['location_selector'].set_city(None)
                    
        elif self.current_state == 'location_selector':
            if isinstance(result, dict) and result.get('action') == 'visit_location':
                self.current_state = 'job_board'
                if 'job_board' in self.states:
                    self.states['job_board'].refresh_jobs(
                        result['city'],
                        0,  # Default level
                        result['location']
                    )
                    
        elif self.current_state == 'job_board':
            if result == "accept_job":
                self.current_state = 'route_selection'
                if 'route_selection' in self.states:
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

    def start_game(self, location_data):
        # Stop menu music
        self.sound_manager.stop_menu_music()
        
        # Initialize tutorial manager
        player_data = {
            'visited_location_types': set(),
            'current_city': location_data['city']
        }
        tutorial_manager = TutorialManager(self.screen, self.tts_engine, player_data)
        
        # Start tutorial messages
        print("\nStarting tutorial initialization...")
        tutorial_manager.update_objective("start_tutorial")
        print("Tutorial initialization complete")
        
        # Initialize driving state with selected location and tutorial
        self.states['driving'] = DrivingState(
            screen=self.screen,
            tts_engine=self.tts_engine,
            sound_manager=self.sound_manager,
            settings=self.settings,
            start_city=location_data['city'],
            start_location=location_data['location']
        )
        self.states['driving'].tutorial_manager = tutorial_manager
        self.current_state = 'driving'

if __name__ == "__main__":
    try:
        print("Creating game instance...")
        game = FreightFate()
        print("Starting game loop...")
        game.run()
    except Exception as e:
        print(f"\nError occurred: {e}")
        import traceback
        traceback.print_exc()
