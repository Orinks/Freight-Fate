import json
import os

def get_available_routes(start_city=None):
    """Get all available routes, optionally filtered by start city."""
    cities_path = os.path.join(os.path.dirname(__file__), 'cities.json')
    with open(cities_path, 'r') as f:
        data = json.load(f)
    
    routes = data.get('routes', [])
    if start_city:
        routes = [r for r in routes if r['start'] == start_city]
    return routes

def find_route(start_city, end_city):
    """Find a specific route between two cities."""
    routes = get_available_routes()
    for route in routes:
        if route['start'] == start_city and route['end'] == end_city:
            return route
    return None
