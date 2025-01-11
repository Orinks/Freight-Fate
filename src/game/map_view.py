import pygame
from typing import Dict, List, Optional

class MapView:
    def __init__(self, screen, tts_engine, cities_data: Dict):
        self.screen = screen
        self.tts_engine = tts_engine
        self.cities_data = cities_data
        self.font = pygame.font.Font(None, 32)
        
        # Colors
        self.WHITE = (255, 255, 255)
        self.BLACK = (0, 0, 0)
        self.GRAY = (128, 128, 128)
        self.YELLOW = (255, 255, 0)
        
        # State
        self.selected_city_index = 0
        # Convert cities dictionary to list
        self.cities = list(cities_data['cities'].keys())
        
        # Initialize with TTS announcement
        if self.tts_engine:
            self.tts_engine.output("Map view opened. Use arrow keys to navigate between cities. Press Enter to select a city. Press M or Escape to close map.")
            
    def handle_event(self, event) -> Optional[str]:
        """Handle input events."""
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_UP:
                self.select_previous_city()
            elif event.key == pygame.K_DOWN:
                self.select_next_city()
            elif event.key == pygame.K_RETURN:
                return self.select_city()
            elif event.key in (pygame.K_ESCAPE, pygame.K_m):
                self.tts_engine.output("Closing map")
                return 'close'
            elif event.key == pygame.K_TAB:
                self.announce_help()
        return None
        
    def select_previous_city(self):
        """Select the previous city in the list."""
        if self.cities:
            self.selected_city_index = (self.selected_city_index - 1) % len(self.cities)
            self.announce_current_city()
            
    def select_next_city(self):
        """Select the next city in the list."""
        if self.cities:
            self.selected_city_index = (self.selected_city_index + 1) % len(self.cities)
            self.announce_current_city()
            
    def select_city(self) -> Optional[str]:
        """Select the current city."""
        if self.cities:
            city = self.cities[self.selected_city_index]
            self.tts_engine.output(f"Selected {city}")
            return f"select_city:{city}"
        return None
        
    def announce_current_city(self):
        """Announce the currently selected city."""
        if self.cities:
            city = self.cities[self.selected_city_index]
            city_data = self.cities_data['cities'].get(city, {})
            job_locations = len(city_data.get('job_locations', {}).get('truck_stops', [])) if city_data else 0
            job_locations += len(city_data.get('job_locations', {}).get('freight_terminals', [])) if city_data else 0
            job_locations += len(city_data.get('job_locations', {}).get('distribution_centers', [])) if city_data else 0
            self.tts_engine.output(f"{city}. {job_locations} job locations available.")
            
    def announce_help(self):
        """Announce help information."""
        help_text = (
            "Map controls: "
            "Use up and down arrows to move between cities. "
            "Press Enter to select a city. "
            "Press M or Escape to close the map. "
            "Press Tab to hear these instructions again."
        )
        self.tts_engine.output(help_text)
        
    def render(self):
        """Render the map view."""
        self.screen.fill(self.BLACK)
        
        # Draw title
        title = self.font.render("Map View", True, self.WHITE)
        title_rect = title.get_rect(center=(self.screen.get_width() // 2, 50))
        self.screen.blit(title, title_rect)
        
        # Draw cities list
        y_position = 100
        for i, city in enumerate(self.cities):
            color = self.YELLOW if i == self.selected_city_index else self.WHITE
            prefix = "→ " if i == self.selected_city_index else "  "
            
            city_data = self.cities_data['cities'].get(city, {})
            job_locations = len(city_data.get('job_locations', {}).get('truck_stops', [])) if city_data else 0
            job_locations += len(city_data.get('job_locations', {}).get('freight_terminals', [])) if city_data else 0
            job_locations += len(city_data.get('job_locations', {}).get('distribution_centers', [])) if city_data else 0
            
            text = f"{prefix}{city} ({job_locations} locations)"
            
            text_surface = self.font.render(text, True, color)
            text_rect = text_surface.get_rect(left=50, top=y_position)
            self.screen.blit(text_surface, text_rect)
            y_position += 40
        
        # Draw instructions
        instructions = [
            "↑/↓: Navigate Cities",
            "ENTER: Select City",
            "M/ESC: Close Map",
            "TAB: Help"
        ]
        y_position = self.screen.get_height() - 150
        for instruction in instructions:
            text = self.font.render(instruction, True, self.GRAY)
            text_rect = text.get_rect(center=(self.screen.get_width() // 2, y_position))
            self.screen.blit(text, text_rect)
            y_position += 30
            
        pygame.display.flip()

