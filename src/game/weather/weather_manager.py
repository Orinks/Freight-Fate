from datetime import datetime, timedelta
import random
from typing import Dict, List, Optional, Tuple
from .weather_system import WeatherSystem, WeatherType

class WeatherManager:
    def __init__(self):
        self.weather_system = WeatherSystem()
        self.last_weather_change = datetime.now()
        self.weather_duration = timedelta(minutes=15)  # Base duration
        
        # Weather transition probabilities
        self.transition_matrix = {
            WeatherType.CLEAR: {
                WeatherType.CLEAR: 0.7,
                WeatherType.CLOUDY: 0.2,
                WeatherType.FOG: 0.1
            },
            WeatherType.CLOUDY: {
                WeatherType.CLEAR: 0.3,
                WeatherType.CLOUDY: 0.4,
                WeatherType.RAIN: 0.2,
                WeatherType.FOG: 0.1
            },
            WeatherType.RAIN: {
                WeatherType.CLOUDY: 0.3,
                WeatherType.RAIN: 0.4,
                WeatherType.HEAVY_RAIN: 0.3
            },
            WeatherType.HEAVY_RAIN: {
                WeatherType.RAIN: 0.6,
                WeatherType.HEAVY_RAIN: 0.4
            },
            WeatherType.SNOW: {
                WeatherType.SNOW: 0.6,
                WeatherType.BLIZZARD: 0.2,
                WeatherType.CLOUDY: 0.2
            },
            WeatherType.BLIZZARD: {
                WeatherType.SNOW: 0.7,
                WeatherType.BLIZZARD: 0.3
            },
            WeatherType.FOG: {
                WeatherType.FOG: 0.4,
                WeatherType.CLEAR: 0.3,
                WeatherType.CLOUDY: 0.3
            }
        }
        
        # Season-based weather preferences
        self.seasonal_weights = {
            'spring': {
                WeatherType.CLEAR: 0.3,
                WeatherType.CLOUDY: 0.3,
                WeatherType.RAIN: 0.2,
                WeatherType.HEAVY_RAIN: 0.1,
                WeatherType.FOG: 0.1
            },
            'summer': {
                WeatherType.CLEAR: 0.5,
                WeatherType.CLOUDY: 0.2,
                WeatherType.RAIN: 0.2,
                WeatherType.HEAVY_RAIN: 0.1
            },
            'autumn': {
                WeatherType.CLOUDY: 0.3,
                WeatherType.RAIN: 0.3,
                WeatherType.HEAVY_RAIN: 0.2,
                WeatherType.FOG: 0.2
            },
            'winter': {
                WeatherType.CLOUDY: 0.2,
                WeatherType.SNOW: 0.4,
                WeatherType.BLIZZARD: 0.2,
                WeatherType.FOG: 0.2
            }
        }
    
    def get_current_season(self) -> str:
        """Get current season based on date."""
        month = datetime.now().month
        if 3 <= month <= 5:
            return 'spring'
        elif 6 <= month <= 8:
            return 'summer'
        elif 9 <= month <= 11:
            return 'autumn'
        else:
            return 'winter'
    
    def choose_next_weather(self) -> WeatherType:
        """Choose next weather type based on current conditions and season."""
        current_type = self.weather_system.current_condition.type
        season = self.get_current_season()
        
        # Get transition probabilities for current weather
        base_probabilities = self.transition_matrix.get(
            current_type,
            {WeatherType.CLEAR: 1.0}
        )
        
        # Adjust probabilities based on season
        seasonal_prefs = self.seasonal_weights[season]
        adjusted_probabilities = {}
        
        for weather_type, prob in base_probabilities.items():
            seasonal_weight = seasonal_prefs.get(weather_type, 0.1)
            adjusted_probabilities[weather_type] = prob * seasonal_weight
        
        # Normalize probabilities
        total = sum(adjusted_probabilities.values())
        if total > 0:
            adjusted_probabilities = {
                k: v/total for k, v in adjusted_probabilities.items()
            }
        
        # Choose next weather
        r = random.random()
        cumulative = 0
        for weather_type, prob in adjusted_probabilities.items():
            cumulative += prob
            if r <= cumulative:
                return weather_type
        
        return WeatherType.CLEAR  # Fallback
    
    def update(self, dt: float, camera_pos: Tuple[float, float] = (0, 0)):
        """Update weather system and manage weather changes."""
        current_time = datetime.now()
        
        # Check if it's time for weather change
        if current_time - self.last_weather_change >= self.weather_duration:
            next_weather = self.choose_next_weather()
            
            # Transition duration based on weather types
            transition_duration = random.uniform(60, 180)  # 1-3 minutes
            self.weather_system.transition_to(next_weather, transition_duration)
            
            # Set next weather change time
            self.last_weather_change = current_time
            # Randomize next duration
            base_minutes = 15
            variation = random.uniform(-5, 5)
            self.weather_duration = timedelta(minutes=base_minutes + variation)
        
        # Update weather system
        self.weather_system.update(dt, camera_pos)
    
    def get_physics_modifiers(self) -> Dict[str, float]:
        """Get current weather effects on physics."""
        return self.weather_system.physics_modifiers
    
    def render(self, surface):
        """Render weather effects."""
        self.weather_system.render(surface)
    
    def get_weather_report(self) -> str:
        """Get detailed weather report including forecast."""
        current = self.weather_system.current_condition
        time_until_change = (
            self.last_weather_change +
            self.weather_duration -
            datetime.now()
        ).total_seconds() / 60
        
        return (
            f"Current Weather Report:\n"
            f"{self.weather_system.get_status_text()}\n"
            f"Expected duration: {time_until_change:.0f} minutes\n"
            f"Season: {self.get_current_season().capitalize()}"
        )
