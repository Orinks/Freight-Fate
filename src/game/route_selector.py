import pygame
import json
import os
from typing import Dict, Optional
from data.routes import get_available_routes, find_route

# Get the absolute path to cities.json
CITIES_JSON_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'data', 'cities.json')

class RouteSelector:
    def __init__(self, screen, tts_engine):
        self.screen = screen
        self.tts_engine = tts_engine
        self.font = pygame.font.Font(None, 36)
        self.small_font = pygame.font.Font(None, 24)
        
        # Load city and highway data
        with open(CITIES_JSON_PATH, 'r') as f:
            data = json.load(f)
            cities_list = data['cities']
            self.cities = {city['name']: city for city in cities_list}
            self.highways = data.get('highways', {})
        
        # Set initial state
        self.current_city = list(self.cities.keys())[0]
        self.selected_route = None
        self.available_routes = []
        self.update_available_routes()

    def update_available_routes(self):
        """Update available routes based on current city"""
        self.available_routes = get_available_routes(self.current_city)

    def render(self):
        self.screen.fill((0, 0, 0))
        
        # Render current city
        city_text = self.font.render(f"Current City: {self.current_city}", True, (255, 255, 255))
        self.screen.blit(city_text, (20, 20))

        # Render available highways
        y_pos = 80
        for i, route in enumerate(self.available_routes):
            highway = route['highway']
            desc = route['description']
            conditions = route['conditions']
            
            # Highlight selected route
            color = (255, 255, 0) if route == self.selected_route else (255, 255, 255)
            
            # Highway name and description
            highway_text = self.font.render(f"{highway}: {desc}", True, color)
            self.screen.blit(highway_text, (20, y_pos))
            
            # Conditions
            condition_text = self.small_font.render(
                f"Traffic: {conditions['traffic']} | Terrain: {conditions['terrain']} | Stops: {conditions['truck_stops']}",
                True, (200, 200, 200)
            )
            self.screen.blit(condition_text, (20, y_pos + 30))
            
            # Available destinations on this highway
            destinations = [city for city in self.cities if highway in self.cities[city]['highways']]
            dest_text = self.small_font.render(f"Destinations: {', '.join(destinations)}", True, (200, 200, 200))
            self.screen.blit(dest_text, (20, y_pos + 55))
            
            y_pos += 100

        pygame.display.flip()

    def handle_event(self, event):
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_UP:
                self.select_previous_route()
            elif event.key == pygame.K_DOWN:
                self.select_next_route()
            elif event.key == pygame.K_RETURN:
                return self.confirm_route()
        return None

    def select_previous_route(self):
        if self.available_routes:
            current_idx = self.available_routes.index(self.selected_route) if self.selected_route else 0
            new_idx = (current_idx - 1) % len(self.available_routes)
            self.selected_route = self.available_routes[new_idx]
            self.speak_route_info()

    def select_next_route(self):
        if self.available_routes:
            current_idx = self.available_routes.index(self.selected_route) if self.selected_route else -1
            new_idx = (current_idx + 1) % len(self.available_routes)
            self.selected_route = self.available_routes[new_idx]
            self.speak_route_info()

    def speak_route_info(self):
        if self.selected_route:
            route = self.selected_route
            info = f"{route['highway']}. {route['description']}. "
            info += f"Traffic is {route['conditions']['traffic']}. "
            info += f"Terrain is {route['conditions']['terrain']}. "
            info += f"Truck stops are {route['conditions']['truck_stops']}."
            self.tts_engine.output(info)

    def confirm_route(self):
        if self.selected_route:
            return {
                'highway': self.selected_route['highway'],
                'conditions': self.selected_route['conditions']
            }
        return None
