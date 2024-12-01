import json
import os
from collections import defaultdict
import heapq

def load_city_data():
    """Load city data from cities.json"""
    json_path = os.path.join(os.path.dirname(__file__), 'cities.json')
    with open(json_path, 'r') as f:
        return json.load(f)

def build_graph(city_data):
    """Build a graph representation of the city network"""
    graph = defaultdict(dict)
    cities = city_data['cities']
    
    for city, data in cities.items():
        for dest, connection in data.get('connections', {}).items():
            # Add both directions since roads go both ways
            graph[city][dest] = {
                'distance': connection['distance'],
                'highway': connection['highway'],
                'rest_stops': connection.get('rest_stops', [])
            }
            graph[dest][city] = {
                'distance': connection['distance'],
                'highway': connection['highway'],
                'rest_stops': connection.get('rest_stops', [])
            }
    
    return graph

def find_route(start_city, end_city, prefer_highway=None):
    """Find the shortest route between two cities, optionally preferring a specific highway
    
    Args:
        start_city (str): Starting city name
        end_city (str): Destination city name
        prefer_highway (str, optional): Preferred highway (e.g., "I-95")
        
    Returns:
        dict: Route information including distance, path, highways used, and rest stops
    """
    city_data = load_city_data()
    graph = build_graph(city_data)
    
    if start_city not in graph or end_city not in graph:
        return None
    
    # Initialize distances and paths
    distances = {city: float('infinity') for city in graph}
    distances[start_city] = 0
    previous = {city: None for city in graph}
    rest_stops = {city: [] for city in graph}
    highways = {city: [] for city in graph}
    
    # Priority queue for Dijkstra's algorithm
    pq = [(0, start_city)]
    
    while pq:
        current_distance, current_city = heapq.heappop(pq)
        
        if current_city == end_city:
            break
            
        if current_distance > distances[current_city]:
            continue
            
        for next_city, connection in graph[current_city].items():
            distance = connection['distance']
            highway = connection['highway']
            
            # Apply preference for specified highway
            if prefer_highway and highway != prefer_highway:
                distance *= 1.2  # Penalty for not using preferred highway
                
            new_distance = distances[current_city] + distance
            
            if new_distance < distances[next_city]:
                distances[next_city] = new_distance
                previous[next_city] = current_city
                rest_stops[next_city] = rest_stops[current_city] + connection.get('rest_stops', [])
                highways[next_city] = highways[current_city] + [highway]
                heapq.heappush(pq, (new_distance, next_city))
    
    if distances[end_city] == float('infinity'):
        return None
        
    # Build the path
    path = []
    current = end_city
    while current:
        path.append(current)
        current = previous[current]
    path.reverse()
    
    # Get unique highways used
    route_highways = list(dict.fromkeys(highways[end_city]))
    
    return {
        'distance': distances[end_city],
        'path': path,
        'highways': route_highways,
        'rest_stops': rest_stops[end_city]
    }

def get_highway_info(highway_id):
    """Get detailed information about a specific highway"""
    city_data = load_city_data()
    highways = city_data.get('highways', {})
    return highways.get(highway_id, None)

def get_available_routes(city):
    """Get all available routes from a given city"""
    city_data = load_city_data()
    cities = city_data['cities']
    
    if city not in cities:
        return []
        
    routes = []
    city_data = cities[city]
    
    for highway in city_data.get('highways', []):
        highway_info = get_highway_info(highway)
        if highway_info:
            routes.append({
                'highway': highway,
                'description': highway_info['description'],
                'conditions': {
                    'traffic': highway_info.get('traffic', 'unknown'),
                    'terrain': highway_info.get('terrain', 'unknown'),
                    'truck_stops': highway_info.get('truck_stops', 'unknown')
                }
            })
    
    return routes
