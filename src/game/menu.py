import pygame
import threading
from typing import Dict, List, Optional, Callable

class MenuItem:
    def __init__(self, text: str, action: str, visible_when: Optional[Callable[[], bool]] = None):
        self.text = text
        self.action = action
        self.visible_when = visible_when or (lambda: True)

class MenuSection:
    def __init__(self, title: str, items: List[MenuItem]):
        self.title = title
        self.items = items
        
    def get_visible_items(self) -> List[MenuItem]:
        """Get list of currently visible items in this section."""
        return [item for item in self.items if item.visible_when()]

class Menu:
    def __init__(self, screen, tts_engine, sound_manager=None, cities_data=None, speech_status="active"):
        """Initialize the menu."""
        self.screen = screen
        self.tts_engine = tts_engine
        self.sound_manager = sound_manager
        self.cities_data = cities_data
        self.speech_status = speech_status
        self.font = pygame.font.Font(None, 36)
        self.small_font = pygame.font.Font(None, 24)
        
        # Colors
        self.WHITE = (255, 255, 255)
        self.BLACK = (0, 0, 0)
        self.YELLOW = (255, 255, 0)
        self.GRAY = (128, 128, 128)
        self.RED = (255, 0, 0)
        self.GREEN = (0, 255, 0)
        self.ORANGE = (255, 165, 0)
        
        # Menu states
        self.states = {
            'main': self.create_main_menu(),
            'location': self.create_location_menu()
        }
        self.current_state = 'main'
        self.selected_index = 0  # Add selected index to track current selection
        
        # Initial announcement
        if self.tts_engine:
            self.tts_engine.output("Main Menu. Use arrow keys to navigate, Enter to select, Tab for help.")
        
        print("Menu initialized")
        
    def create_main_menu(self):
        """Create the main menu items."""
        return MenuSection('Freight Fate', [
            MenuItem('New Game', 'new_game'),
            MenuItem('Load Game', 'load_game'),
            MenuItem('Settings', 'settings'),
            MenuItem('Exit', 'exit')
        ])
        
    def create_location_menu(self):
        """Create the location selection menu."""
        locations = []
        if self.cities_data and 'cities' in self.cities_data:
            for city in self.cities_data['cities']:
                for location in city['locations']:
                    locations.append(MenuItem(
                        f"{city['name']} - {location['name']} ({location['type']}) - {', '.join(location['cargo_types'])}",
                        {
                            'action': 'visit_location',
                            'city': city['name'],
                            'location': {
                                'name': location['name'],
                                'type': location['type'],
                                'cargo_types': location['cargo_types']
                            }
                        }
                    ))

        return MenuSection('Select Starting Location', locations)
        
    def get_current_menu(self):
        """Get the current menu state."""
        return self.states[self.current_state]
        
    def announce_current_item(self):
        """Announce the currently selected menu item."""
        if not self.tts_engine:
            return
            
        current_state = self.states[self.current_state]
        visible_items = current_state.get_visible_items()
        if visible_items:
            current_item = visible_items[self.selected_index]
            self.tts_engine.output(current_item.text)
        
    def speak_current_item(self):
        """Announce the currently selected menu item."""
        menu = self.get_current_menu()
        if not menu.get_visible_items():
            return
            
        current_item = menu.get_visible_items()[0]
        self.tts_engine.output(current_item.text)
        
    def play_sound(self, sound_name: str):
        """Play a sound effect if sound manager exists."""
        if self.sound_manager:
            self.sound_manager.play_sound(sound_name)
            
    def handle_input(self, event):
        """Handle input events."""
        if event.type == pygame.KEYDOWN:
            if event.key in [pygame.K_UP, pygame.K_DOWN]:
                # Play navigation sound
                if self.sound_manager:
                    self.sound_manager.play_sound('menu_nav')
                    
                # Update selection
                direction = -1 if event.key == pygame.K_UP else 1
                current_state = self.states[self.current_state]
                visible_items = current_state.get_visible_items()
                if visible_items:
                    self.selected_index = (self.selected_index + direction) % len(visible_items)
                    if self.tts_engine:
                        current_item = visible_items[self.selected_index]
                        # Add more context for certain items
                        if current_item.text == "New Game":
                            self.tts_engine.output("New Game - Start a new trucking career")
                        elif current_item.text == "Load Game":
                            self.tts_engine.output("Load Game - Continue your previous journey")
                        elif current_item.text == "Settings":
                            self.tts_engine.output("Settings - Adjust game options")
                        elif current_item.text == "Exit":
                            self.tts_engine.output("Exit - Close the game")
                        else:
                            self.tts_engine.output(current_item.text)
                    
            elif event.key == pygame.K_RETURN:
                # Play selection sound
                if self.sound_manager:
                    self.sound_manager.play_sound('menu_select')
                    
                # Handle selection
                current_state = self.states[self.current_state]
                visible_items = current_state.get_visible_items()
                if not visible_items:
                    return None
                    
                selected_item = visible_items[self.selected_index]
                
                if self.current_state == 'main':
                    if selected_item.action == 'new_game':
                        self.current_state = 'location'
                        self.selected_index = 0  # Reset selection for new menu
                        if self.tts_engine:
                            self.tts_engine.output("Location Selection. Choose your starting point. Press Space for location details, Tab for help.")
                    elif selected_item.action == 'settings':
                        if self.sound_manager:
                            self.sound_manager.play_sound('menu_select')
                        return 'settings'
                    elif selected_item.action == 'exit':
                        if self.sound_manager:
                            self.sound_manager.play_sound('menu_select')
                        return 'exit'
                elif self.current_state == 'location':
                    if self.sound_manager:
                        self.sound_manager.play_sound('menu_select')
                    # Pass both city and location data
                    return ('start_game', {
                        'city': selected_item.action['city'],
                        'location': selected_item.action['location']
                    })
                    
            elif event.key == pygame.K_ESCAPE:
                if self.current_state == 'location':
                    # Play back sound and return to main menu
                    if self.sound_manager:
                        self.sound_manager.play_sound('menu_back')
                    self.current_state = 'main'
                    self.selected_index = 0  # Reset selection
                    if self.tts_engine:
                        self.tts_engine.output("Returned to Main Menu. Use arrow keys to navigate, Enter to select.")
                else:
                    # Play back sound when escaping from main menu
                    if self.sound_manager:
                        self.sound_manager.play_sound('menu_back')
                    return 'back'
                    
            elif event.key == pygame.K_SPACE and self.current_state == 'location':
                # Announce location details
                current_state = self.states[self.current_state]
                selected_item = current_state.get_visible_items()[self.selected_index]
                if self.tts_engine and self.cities_data:
                    for city in self.cities_data['cities']:
                        if city['name'] == selected_item.action['city']:
                            details = f"{city['name']} - {selected_item.action['location']['type']}. Available cargo types: {', '.join(selected_item.action['location']['cargo_types'])}"
                            self.tts_engine.output(details)
                            break
                            
            elif event.key == pygame.K_TAB:
                # Announce help information
                if self.tts_engine:
                    if self.current_state == 'main':
                        self.tts_engine.output("Main Menu Controls: Up and Down arrows to navigate options, Enter to select, F1 for detailed help.")
                    else:
                        self.tts_engine.output("Location Selection Controls: Up and Down arrows to browse locations, Space to hear cargo details, Enter to select, Escape to return to main menu.")
                        
            elif event.key == pygame.K_F1:
                # Announce detailed help
                if self.tts_engine:
                    if self.current_state == 'main':
                        help_text = (
                            "Main Menu Help: "
                            "New Game starts a fresh trucking career. "
                            "Load Game continues your previous journey. "
                            "Settings lets you adjust game options. "
                            "Use Up and Down arrows to navigate, "
                            "Enter to select an option, "
                            "Tab for quick help, "
                            "and Escape to go back."
                        )
                    else:
                        help_text = (
                            "Location Selection Help: "
                            "Choose your starting location carefully. "
                            "Each location offers different cargo types and opportunities. "
                            "Use Up and Down arrows to browse locations, "
                            "Space to hear detailed information about cargo types, "
                            "Enter to select your starting point, "
                            "and Escape to return to the main menu."
                        )
                    self.tts_engine.output(help_text)
                    
    def get_speech_status_info(self):
        """Get the speech status text and color."""
        if self.speech_status == "active":
            return "Speech: Active", self.GREEN
        elif self.speech_status == "fallback":
            return "Speech: Fallback Mode", self.ORANGE
        else:
            return "Speech: Disabled", self.RED

    def render(self):
        """Render the current menu state."""
        self.screen.fill(self.BLACK)
        menu = self.get_current_menu()
        
        # Draw title
        title = self.font.render(menu.title, True, self.WHITE)
        title_rect = title.get_rect(center=(self.screen.get_width() // 2, 50))
        self.screen.blit(title, title_rect)

        # Draw speech status indicator
        status_text, status_color = self.get_speech_status_info()
        status_surface = self.small_font.render(status_text, True, status_color)
        status_rect = status_surface.get_rect(topright=(self.screen.get_width() - 10, 10))
        self.screen.blit(status_surface, status_rect)
        
        # Draw menu items
        if self.current_state == 'main':
            # Center menu items vertically
            visible_items = menu.get_visible_items()
            start_y = (self.screen.get_height() - (len(visible_items) * 50)) // 2
            for i, item in enumerate(visible_items):
                color = self.YELLOW if i == self.selected_index else self.WHITE
                text = self.font.render(item.text, True, color)
                text_rect = text.get_rect(center=(self.screen.get_width() // 2, start_y + i * 50))
                self.screen.blit(text, text_rect)
                
        elif self.current_state == 'location':
            # Draw scrollable location list
            visible_items = menu.get_visible_items()
            y_position = 100
            for i, item in enumerate(visible_items):
                is_selected = i == self.selected_index
                prefix = "→ " if is_selected else "  "
                color = self.YELLOW if is_selected else self.WHITE
                text = self.font.render(prefix + item.text, True, color)
                text_rect = text.get_rect(left=50, top=y_position)
                self.screen.blit(text, text_rect)
                y_position += 40
            
            # Draw instructions
            instructions = [
                "Use UP/DOWN arrows to navigate",
                "Press ENTER to select location",
                "Press ESC to return to menu"
            ]
            y_position = self.screen.get_height() - 120
            for instruction in instructions:
                text = self.font.render(instruction, True, self.GRAY)
                text_rect = text.get_rect(center=(self.screen.get_width() // 2, y_position))
                self.screen.blit(text, text_rect)
                y_position += 30
        
        pygame.display.flip()
