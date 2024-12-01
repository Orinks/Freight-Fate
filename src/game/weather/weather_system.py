from dataclasses import dataclass
from enum import Enum, auto
import random
import math
from typing import Dict, List, Optional, Tuple
import pygame
from datetime import datetime, timedelta

class WeatherType(Enum):
    CLEAR = auto()
    CLOUDY = auto()
    RAIN = auto()
    HEAVY_RAIN = auto()
    SNOW = auto()
    BLIZZARD = auto()
    FOG = auto()

@dataclass
class WeatherCondition:
    type: WeatherType
    intensity: float  # 0.0 to 1.0
    temperature: float  # Celsius
    wind_speed: float  # km/h
    wind_direction: float  # degrees (0-360)
    visibility: float  # meters
    road_grip: float  # 0.0 to 1.0
    
    @property
    def is_precipitation(self) -> bool:
        return self.type in {WeatherType.RAIN, WeatherType.HEAVY_RAIN, WeatherType.SNOW, WeatherType.BLIZZARD}

class WeatherSystem:
    def __init__(self):
        self.current_condition = WeatherCondition(
            type=WeatherType.CLEAR,
            intensity=0.0,
            temperature=20.0,
            wind_speed=0.0,
            wind_direction=0.0,
            visibility=10000.0,
            road_grip=1.0
        )
        
        self.target_condition = self.current_condition
        self.transition_time = 0.0
        self.transition_duration = 0.0
        
        # Weather particles
        self.particles: List[Dict] = []
        self.max_particles = 1000
        
        # Weather effects on physics
        self.physics_modifiers = {
            'traction': 1.0,
            'drag': 1.0,
            'visibility': 1.0
        }
        
        # Define weather patterns
        self.weather_patterns = {
            WeatherType.CLEAR: {
                'visibility': (8000, 10000),
                'road_grip': (0.9, 1.0),
                'temperature': (15, 30),
                'wind_speed': (0, 20)
            },
            WeatherType.CLOUDY: {
                'visibility': (6000, 8000),
                'road_grip': (0.8, 0.9),
                'temperature': (10, 25),
                'wind_speed': (10, 30)
            },
            WeatherType.RAIN: {
                'visibility': (3000, 6000),
                'road_grip': (0.6, 0.8),
                'temperature': (5, 20),
                'wind_speed': (20, 40)
            },
            WeatherType.HEAVY_RAIN: {
                'visibility': (1000, 3000),
                'road_grip': (0.4, 0.6),
                'temperature': (5, 15),
                'wind_speed': (30, 60)
            },
            WeatherType.SNOW: {
                'visibility': (2000, 4000),
                'road_grip': (0.3, 0.5),
                'temperature': (-10, 0),
                'wind_speed': (10, 30)
            },
            WeatherType.BLIZZARD: {
                'visibility': (500, 2000),
                'road_grip': (0.1, 0.3),
                'temperature': (-20, -5),
                'wind_speed': (40, 80)
            },
            WeatherType.FOG: {
                'visibility': (100, 2000),
                'road_grip': (0.7, 0.9),
                'temperature': (0, 15),
                'wind_speed': (0, 10)
            }
        }
    
    def generate_weather_condition(self, weather_type: WeatherType) -> WeatherCondition:
        """Generate weather parameters based on weather type."""
        pattern = self.weather_patterns[weather_type]
        
        return WeatherCondition(
            type=weather_type,
            intensity=random.uniform(0.3, 1.0),
            temperature=random.uniform(*pattern['temperature']),
            wind_speed=random.uniform(*pattern['wind_speed']),
            wind_direction=random.uniform(0, 360),
            visibility=random.uniform(*pattern['visibility']),
            road_grip=random.uniform(*pattern['road_grip'])
        )
    
    def transition_to(self, weather_type: WeatherType, duration: float):
        """Start transition to new weather condition."""
        self.target_condition = self.generate_weather_condition(weather_type)
        self.transition_time = 0.0
        self.transition_duration = duration
    
    def update(self, dt: float, camera_pos: Tuple[float, float] = (0, 0)):
        """Update weather system."""
        # Update weather transition
        if self.transition_time < self.transition_duration:
            progress = self.transition_time / self.transition_duration
            # Smooth transition using sine interpolation
            blend = (1 - math.cos(progress * math.pi)) / 2
            
            # Interpolate weather parameters
            self.current_condition = WeatherCondition(
                type=self.target_condition.type,
                intensity=self._lerp(
                    self.current_condition.intensity,
                    self.target_condition.intensity,
                    blend
                ),
                temperature=self._lerp(
                    self.current_condition.temperature,
                    self.target_condition.temperature,
                    blend
                ),
                wind_speed=self._lerp(
                    self.current_condition.wind_speed,
                    self.target_condition.wind_speed,
                    blend
                ),
                wind_direction=self._lerp(
                    self.current_condition.wind_direction,
                    self.target_condition.wind_direction,
                    blend
                ),
                visibility=self._lerp(
                    self.current_condition.visibility,
                    self.target_condition.visibility,
                    blend
                ),
                road_grip=self._lerp(
                    self.current_condition.road_grip,
                    self.target_condition.road_grip,
                    blend
                )
            )
            
            self.transition_time += dt
        
        # Update physics modifiers
        self.physics_modifiers['traction'] = self.current_condition.road_grip
        self.physics_modifiers['drag'] = 1.0 + (
            0.2 * self.current_condition.wind_speed / 100
        )
        self.physics_modifiers['visibility'] = min(
            1.0, self.current_condition.visibility / 10000
        )
        
        # Update weather particles
        self._update_particles(dt, camera_pos)
    
    def _lerp(self, a: float, b: float, t: float) -> float:
        """Linear interpolation between two values."""
        return a + (b - a) * t
    
    def _update_particles(self, dt: float, camera_pos: Tuple[float, float]):
        """Update weather particle positions."""
        if not self.current_condition.is_precipitation:
            self.particles.clear()
            return
        
        # Add new particles if needed
        particle_count = int(self.max_particles * self.current_condition.intensity)
        while len(self.particles) < particle_count:
            self._spawn_particle(camera_pos)
        
        # Update existing particles
        screen_width, screen_height = pygame.display.get_surface().get_size()
        wind_x = math.cos(math.radians(self.current_condition.wind_direction))
        wind_y = math.sin(math.radians(self.current_condition.wind_direction))
        
        for particle in self.particles[:]:
            # Update position
            particle['x'] += (
                wind_x * self.current_condition.wind_speed * dt +
                particle['speed_x'] * dt
            )
            particle['y'] += (
                wind_y * self.current_condition.wind_speed * dt +
                particle['speed_y'] * dt
            )
            
            # Remove if out of bounds
            if (
                particle['y'] > screen_height or
                particle['x'] < 0 or
                particle['x'] > screen_width
            ):
                self.particles.remove(particle)
    
    def _spawn_particle(self, camera_pos: Tuple[float, float]):
        """Spawn a new weather particle."""
        screen_width, screen_height = pygame.display.get_surface().get_size()
        
        particle = {
            'x': random.uniform(0, screen_width),
            'y': random.uniform(-100, 0),
            'speed_x': random.uniform(-20, 20),
            'speed_y': random.uniform(100, 200)
        }
        
        if self.current_condition.type in {WeatherType.SNOW, WeatherType.BLIZZARD}:
            particle['speed_y'] *= 0.5  # Snow falls slower
        
        self.particles.append(particle)
    
    def render(self, surface: pygame.Surface):
        """Render weather effects."""
        if not self.current_condition.is_precipitation:
            return
        
        # Draw particles
        color = (200, 200, 255) if self.current_condition.temperature <= 0 else (200, 200, 200)
        size = 2 if self.current_condition.type in {WeatherType.SNOW, WeatherType.BLIZZARD} else 1
        
        for particle in self.particles:
            pygame.draw.circle(
                surface,
                color,
                (int(particle['x']), int(particle['y'])),
                size
            )
        
        # Apply visibility fog
        fog_surface = pygame.Surface(surface.get_size(), pygame.SRCALPHA)
        fog_alpha = int(255 * (1 - self.physics_modifiers['visibility']))
        fog_surface.fill((200, 200, 200, fog_alpha))
        surface.blit(fog_surface, (0, 0))
    
    def get_status_text(self) -> str:
        """Get human-readable weather status."""
        return (
            f"Weather: {self.current_condition.type.name}\n"
            f"Temperature: {self.current_condition.temperature:.1f}°C\n"
            f"Wind: {self.current_condition.wind_speed:.1f} km/h\n"
            f"Visibility: {self.current_condition.visibility:.0f}m\n"
            f"Road Grip: {self.current_condition.road_grip:.2f}"
        )
