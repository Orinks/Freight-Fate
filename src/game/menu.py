import pygame
import threading
from typing import Dict, List, Optional

class MenuItem:
    def __init__(self, text: str, action: str):
        self.text = text
        self.action = action

class Menu:
    def __init__(self, screen, tts_engine, sound_manager=None, cities_data=None):
        """Initialize the menu."""
        self.screen = screen
        self.tts_engine = tts_engine
        self.sound_manager = sound_manager
        self.cities_data = cities_data
        self.font = pygame.font.Font(None, 36)
        
        # Colors
        self.WHITE = (255, 255, 255)
        self.BLACK = (0, 0, 0)
        self.YELLOW = (255, 255, 0)
        self.GRAY = (128, 128, 128)
        
        # Menu states
        self.states = {
            'main': self.create_main_menu(),
            'location': self.create_location_menu()
        }
        self.current_state = 'main'
        
        print("Menu initialized")
        
    def create_main_menu(self):
        """Create the main menu items."""
        return {
            'items': [
                MenuItem('New Game', 'new_game'),
                MenuItem('Load Game', 'load_game'),
                MenuItem('Settings', 'settings'),
                MenuItem('Exit', 'exit')
            ],
            'selected_index': 0,
            'title': 'Freight Fate'
        }
        
    def create_location_menu(self):
        """Create the location selection menu."""
        locations = []
        if self.cities_data and 'cities' in self.cities_data:
            for city in self.cities_data['cities']:
                for location in city['locations']:
                    locations.append(MenuItem(
                        f"{location['name']} ({location['type']}) - {', '.join(location['cargo_types'])}",
                        {
                            'city': city['name'],
                            'location': {
                                'name': location['name'],
                                'type': location['type'],
                                'cargo_types': location['cargo_types']
                            }
                        }
                    ))
        
        return {
            'items': locations,
            'selected_index': 0,
            'title': 'Select Starting Location',
            'scroll_position': 0,
            'visible_lines': (self.screen.get_height() - 250) // 40
        }
        
    def get_current_menu(self):
        """Get the current menu state."""
        return self.states[self.current_state]
        
    def announce_current_item(self):
        """Announce the currently selected menu item."""
        if not self.tts_engine:
            return
            
        current_state = self.states[self.current_state]
        current_item = current_state['items'][current_state['selected_index']]
        self.tts_engine.output(current_item.text)
        
    def speak_current_item(self):
        """Announce the currently selected menu item."""
        menu = self.get_current_menu()
        if not menu['items']:
            return
            
        current_item = menu['items'][menu['selected_index']]
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
                current_state['selected_index'] = (current_state['selected_index'] + direction) % len(current_state['items'])
                
                # Announce selected item
                self.announce_current_item()
                    
            elif event.key == pygame.K_RETURN:
                # Play selection sound
                if self.sound_manager:
                    self.sound_manager.play_sound('menu_select')
                    
                # Handle selection
                current_state = self.states[self.current_state]
                selected_item = current_state['items'][current_state['selected_index']]
                
                if self.current_state == 'main':
                    if selected_item.action == 'new_game':
                        self.current_state = 'location'
                        if self.tts_engine:
                            self.tts_engine.output("Select your starting location")
                    elif selected_item.action == 'settings':
                        return 'settings'
                    elif selected_item.action == 'exit':
                        return 'exit'
                elif self.current_state == 'location':
                    return ('start_game', selected_item.action)
                    
            elif event.key == pygame.K_ESCAPE and self.current_state == 'location':
                # Play back sound and return to main menu
                if self.sound_manager:
                    self.sound_manager.play_sound('menu_back')
                self.current_state = 'main'
                if self.tts_engine:
                    self.tts_engine.output("Main Menu")
                    
            elif event.key == pygame.K_SPACE and self.current_state == 'location':
                # Announce location details
                current_state = self.states[self.current_state]
                selected_item = current_state['items'][current_state['selected_index']]
                if self.tts_engine and self.cities_data:
                    for city in self.cities_data['cities']:
                        if city['name'] == selected_item.action['city']:
                            details = f"{city['name']}. Population: {city['population']}. Description: {city['description']}"
                            self.tts_engine.output(details)
                            break
                            
            elif event.key == pygame.K_TAB:
                # Announce help information
                if self.tts_engine:
                    if self.current_state == 'main':
                        self.tts_engine.output("Use up and down arrows to navigate, Enter to select, F1 for help")
                    else:
                        self.tts_engine.output("Use up and down arrows to navigate locations, Space for details, Enter to select, Escape to return to main menu, F1 for help")
                        
            elif event.key == pygame.K_F1:
                # Announce detailed help
                if self.tts_engine:
                    help_text = (
                        "Game Controls: "
                        "Use Up and Down arrows to navigate through options. "
                        "Press Enter to select an option. "
                        "Press Space to hear location details. "
                        "Press Tab for panel information. "
                        "Press F1 for this help message. "
                        "Press Escape to return to the main menu."
                    )
                    self.tts_engine.output(help_text)
                    
    def render(self):
        """Render the current menu state."""
        self.screen.fill(self.BLACK)
        menu = self.get_current_menu()
        
        # Draw title
        title = self.font.render(menu['title'], True, self.WHITE)
        title_rect = title.get_rect(center=(self.screen.get_width() // 2, 50))
        self.screen.blit(title, title_rect)
        
        # Draw menu items
        if self.current_state == 'main':
            # Center menu items vertically
            start_y = (self.screen.get_height() - (len(menu['items']) * 50)) // 2
            for i, item in enumerate(menu['items']):
                color = self.YELLOW if i == menu['selected_index'] else self.WHITE
                text = self.font.render(item.text, True, color)
                text_rect = text.get_rect(center=(self.screen.get_width() // 2, start_y + i * 50))
                self.screen.blit(text, text_rect)
                
        elif self.current_state == 'location':
            # Draw scrollable location list
            y_position = 100
            visible_items = menu['items'][menu['scroll_position']:menu['scroll_position'] + menu['visible_lines']]
            for i, item in enumerate(visible_items):
                is_selected = menu['scroll_position'] + i == menu['selected_index']
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
