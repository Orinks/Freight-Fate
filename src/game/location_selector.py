import pygame
from typing import Dict, List, Optional
from .ui_elements import Button, TextBox

class LocationSelector:
    def __init__(self, screen, tts_engine, cities_data: List, sound_manager=None):
        self.screen = screen
        self.tts_engine = tts_engine
        self.cities_data = cities_data
        self.sound_manager = sound_manager
        self.font = pygame.font.Font(None, 32)
        
        # Colors
        self.WHITE = (255, 255, 255)
        self.BLACK = (0, 0, 0)
        self.GRAY = (128, 128, 128)
        self.YELLOW = (255, 255, 0)
        
        # UI Elements
        self.details_box = TextBox(
            self.screen,
            (self.screen.get_width() - 200, 150),
            (180, 300),
            self.WHITE,
            self.BLACK
        )
        
        # State variables
        self.current_city = None
        self.selected_location = None
        self.selected_index = 0
        self.available_locations = []
        self.scroll_position = 0
        self.visible_lines = (self.screen.get_height() - 250) // 40  # Number of visible locations
        
    def set_city(self, city_name: str):
        """Set the current city and load its job locations."""
        self.current_city = city_name
        self.load_locations()
        self.speak_location_count()
        
    def speak_location_count(self):
        """Speak the number of available locations."""
        if self.tts_engine:
            count = len(self.available_locations)
            if count > 0:
                self.tts_engine.output(f"{count} locations available in {self.current_city}.")
            else:
                self.tts_engine.output(f"No locations found in {self.current_city}")

    def speak_current_location(self):
        """Announce the currently selected location and its details."""
        if not self.selected_location:
            self.tts_engine.output("No location selected")
            return
            
        # Just announce the location details without the count
        selection_text = self.format_location_item(self.selected_location)
        self.tts_engine.output(selection_text)
        
    def speak_location_details(self):
        """Announce detailed information about the current location."""
        if not self.selected_location:
            return
            
        details = self.format_location_details(self.selected_location)
        # Replace visual formatting with more natural speech
        details = details.replace("-", "").replace("\n", ". ")
        self.tts_engine.output(details)
        
    def announce_panel_info(self):
        """Announce information about the locations panel."""
        if not self.current_city:
            return
        self.tts_engine.output(
            f"Select your starting location in {self.current_city}. "
            f"{len(self.available_locations)} locations available. "
            "Use up and down arrows to navigate. "
            "Press F1 for help."
        )
        
    def load_locations(self):
        """Load all job locations in the current city."""
        print("Loading locations...")
        if not self.current_city:
            print("No current city set")
            return
            
        # Find the city in the cities list
        city_data = next((city for city in self.cities_data if city['name'] == self.current_city), None)
        if not city_data:
            print(f"City {self.current_city} not found in data")
            return
            
        # Load locations from the city data
        self.available_locations = city_data.get('locations', [])
        print(f"Found {len(self.available_locations)} locations")
        
        # Select the first location by default
        if self.available_locations:
            print("Selecting first location")
            self.selected_location = self.available_locations[0]
            self.selected_index = 0
            self.update_details()
            self.speak_current_location()
        else:
            print("No locations available")
            self.selected_location = None
            self.selected_index = -1
        
    def format_location_item(self, location: Dict, selected: bool = False) -> str:
        """Format a location for display in the list."""
        return (
            f"{location['name']} ({location['type']}) - {', '.join(location['cargo_types'])}"
        )
        
    def format_location_details(self, location) -> str:
        """Format the detailed information for a location."""
        details = [
            f"Name: {location['name']}",
            f"Type: {location['type']}",
            f"Cargo Types: {', '.join(location['cargo_types'])}",
            "",
            "Location Information:",
            "- This is a major freight hub",
            f"- Handles {', '.join(location['cargo_types'])} cargo",
            f"- {self.get_location_description(location)}"
        ]
        return "\n".join(details)
        
    def get_location_description(self, location) -> str:
        """Get a description based on the location type."""
        type_descriptions = {
            'warehouse': 'Large storage facility for temporary cargo storage',
            'distribution': 'Central hub for distributing goods to retailers',
            'industrial': 'Manufacturing and processing facility',
            'retail': 'Direct-to-consumer delivery point'
        }
        return type_descriptions.get(location['type'], 'Standard freight location')
        
    def render(self):
        """Render the location selector interface."""
        # Clear screen with background color
        self.screen.fill(self.BLACK)
        
        # Draw title
        print("Drawing title...")
        title = self.font.render(f"Locations in {self.current_city}", True, self.WHITE)
        title_rect = title.get_rect(center=(self.screen.get_width() // 2, 50))
        self.screen.blit(title, title_rect)
        
        # Draw locations
        print("Drawing locations...")
        y_position = 100
        for i, location in enumerate(self.available_locations[self.scroll_position:self.scroll_position + self.visible_lines]):
            # Format the location text
            location_text = self.format_location_item(location)
            print(f"Location {i}: {location_text}")
            # Add selection indicator
            if i == self.selected_index - self.scroll_position:
                location_text = "→ " + location_text
            else:
                location_text = "  " + location_text
            
            text_surface = self.font.render(location_text, True, 
                                          self.YELLOW if i == self.selected_index - self.scroll_position else self.WHITE)
            text_rect = text_surface.get_rect(left=50, top=y_position)
            self.screen.blit(text_surface, text_rect)
            y_position += 40
        
        # Draw details box
        print("Drawing details...")
        if self.selected_location:
            details = self.format_location_details(self.selected_location)
            print(f"Details: {details}")
            details_lines = details.split('\n')
            y_position = 100
            for line in details_lines:
                text_surface = self.font.render(line, True, self.WHITE)
                text_rect = text_surface.get_rect(left=self.screen.get_width() - 300, top=y_position)
                self.screen.blit(text_surface, text_rect)
                y_position += 30
        else:
            print("No location selected")
        
        # Draw instructions
        print("Drawing instructions...")
        instructions = [
            "Use UP/DOWN arrows to navigate",
            "Press ENTER to select location",
            "Press ESC to return to menu"
        ]
        y_position = self.screen.get_height() - 120
        for instruction in instructions:
            text_surface = self.font.render(instruction, True, self.GRAY)
            text_rect = text_surface.get_rect(center=(self.screen.get_width() // 2, y_position))
            self.screen.blit(text_surface, text_rect)
            y_position += 30
        
        pygame.display.flip()
        
    def handle_event(self, event, current_city=None):
        """Handle pygame events for the location selector."""
        if current_city and current_city != self.current_city:
            self.set_city(current_city)
            # Don't automatically announce panel info
            if self.selected_location:
                self.speak_current_location()
            
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_UP:
                self.select_previous()
            elif event.key == pygame.K_DOWN:
                self.select_next()
            elif event.key == pygame.K_RETURN:
                if self.selected_location:
                    if self.sound_manager:
                        self.sound_manager.play_sound('select')
                    self.tts_engine.output(f"Starting at {self.selected_location['name']}")
                    return True, self.selected_location
            elif event.key == pygame.K_ESCAPE:
                if self.sound_manager:
                    self.sound_manager.play_sound('select')
                self.tts_engine.output("Returning to main menu")
                return True, None
            # Tab key for panel information
            elif event.key == pygame.K_TAB:
                self.announce_panel_info()
            # F1 key for help
            elif event.key == pygame.K_F1:
                help_text = (
                    "Location selector help. "
                    "Use up and down arrow keys to navigate between locations. "
                    "Press Enter to select your starting location. "
                    "Press Space to hear location details. "
                    "Press Tab to hear panel information. "
                    "Press Escape to return to the main menu. "
                    "Press F1 again to repeat this help message."
                )
                self.tts_engine.output(help_text)
            # Space key for location details
            elif event.key == pygame.K_SPACE:
                if self.selected_location:
                    self.speak_location_details()
                
        return False, None
        
    def select_previous(self):
        """Select the previous location in the list."""
        if not self.available_locations:
            return
        self.selected_index = (self.selected_index - 1) % len(self.available_locations)
        if self.selected_index < self.scroll_position:
            self.scroll_position -= 1
        self.selected_location = self.available_locations[self.selected_index]
        if self.sound_manager:
            self.sound_manager.play_sound('click')
        self.speak_current_location()

    def select_next(self):
        """Select the next location in the list."""
        if not self.available_locations:
            return
        self.selected_index = (self.selected_index + 1) % len(self.available_locations)
        if self.selected_index >= self.scroll_position + self.visible_lines:
            self.scroll_position += 1
        self.selected_location = self.available_locations[self.selected_index]
        if self.sound_manager:
            self.sound_manager.play_sound('click')
        self.speak_current_location()
            
    def select_location(self) -> Optional[Dict]:
        """Select the current location to visit."""
        if self.available_locations and 0 <= self.selected_index < len(self.available_locations):
            self.selected_location = self.available_locations[self.selected_index]
            self.speak_location_selected()
            return {
                "action": "visit_location",
                "location": self.selected_location
            }
        return None
        
    def speak_location_selected(self):
        """Speak confirmation of location selection."""
        if self.selected_location:
            text = f"Visiting {self.selected_location['name']}"
            self.tts_engine.output(text)

    def update_details(self):
        """Update the location details box."""
        if self.available_locations and 0 <= self.selected_index < len(self.available_locations):
            details = self.format_location_details(self.available_locations[self.selected_index])
            self.details_box.update(details)
