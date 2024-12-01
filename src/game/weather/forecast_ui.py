import pygame
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import math
from .weather_system import WeatherType, WeatherCondition
from .weather_manager import WeatherManager

class WeatherIcon:
    def __init__(self, size: int):
        self.size = size
        self.surface = pygame.Surface((size, size), pygame.SRCALPHA)
        
        # Cache common colors
        self.WHITE = (255, 255, 255)
        self.GRAY = (128, 128, 128)
        self.BLUE = (64, 128, 255)
        self.DARK_BLUE = (32, 64, 192)
        self.SNOW_COLOR = (240, 240, 255)
        
    def draw_sun(self):
        """Draw sun icon."""
        center = self.size // 2
        radius = self.size // 4
        
        # Draw sun circle
        pygame.draw.circle(self.surface, self.WHITE, (center, center), radius)
        
        # Draw sun rays
        for angle in range(0, 360, 45):
            rad = math.radians(angle)
            start = (
                center + int(math.cos(rad) * (radius + 2)),
                center + int(math.sin(rad) * (radius + 2))
            )
            end = (
                center + int(math.cos(rad) * (radius + 8)),
                center + int(math.sin(rad) * (radius + 8))
            )
            pygame.draw.line(self.surface, self.WHITE, start, end, 2)
    
    def draw_cloud(self, offset: Tuple[int, int] = (0, 0), scale: float = 1.0):
        """Draw cloud shape."""
        base_x, base_y = offset
        radius = int(self.size // 6 * scale)
        
        # Draw cloud circles
        positions = [
            (base_x + radius, base_y + radius),
            (base_x + radius * 2, base_y + radius),
            (base_x + radius * 3, base_y + radius),
            (base_x + radius * 1.5, base_y),
            (base_x + radius * 2.5, base_y)
        ]
        
        for pos in positions:
            pygame.draw.circle(self.surface, self.GRAY, pos, radius)
    
    def draw_rain(self, heavy: bool = False):
        """Draw rain drops."""
        drops = 6 if heavy else 3
        drop_length = 6 if heavy else 4
        
        for i in range(drops):
            x = self.size // 3 + (i * 6)
            y = self.size // 2
            pygame.draw.line(
                self.surface,
                self.BLUE,
                (x, y),
                (x - 2, y + drop_length),
                2
            )
    
    def draw_snow(self, blizzard: bool = False):
        """Draw snowflakes."""
        flakes = 8 if blizzard else 4
        
        for i in range(flakes):
            x = self.size // 4 + (i * 6)
            y = self.size // 2 + (5 if i % 2 == 0 else 0)
            
            # Draw snowflake
            pygame.draw.circle(
                self.surface,
                self.SNOW_COLOR,
                (x, y),
                2
            )
    
    def draw_fog(self):
        """Draw fog waves."""
        for y in range(self.size // 2, self.size, 6):
            for x in range(0, self.size, 12):
                pygame.draw.arc(
                    self.surface,
                    self.WHITE,
                    (x, y, 12, 6),
                    0,
                    math.pi,
                    2
                )
    
    def get_icon(self, weather_type: WeatherType) -> pygame.Surface:
        """Get weather icon surface for weather type."""
        self.surface.fill((0, 0, 0, 0))  # Clear with transparency
        
        if weather_type == WeatherType.CLEAR:
            self.draw_sun()
        elif weather_type == WeatherType.CLOUDY:
            self.draw_cloud()
        elif weather_type == WeatherType.RAIN:
            self.draw_cloud()
            self.draw_rain()
        elif weather_type == WeatherType.HEAVY_RAIN:
            self.draw_cloud()
            self.draw_rain(heavy=True)
        elif weather_type == WeatherType.SNOW:
            self.draw_cloud()
            self.draw_snow()
        elif weather_type == WeatherType.BLIZZARD:
            self.draw_cloud()
            self.draw_snow(blizzard=True)
        elif weather_type == WeatherType.FOG:
            self.draw_fog()
        
        return self.surface.copy()

class WeatherForecastUI:
    def __init__(self, weather_manager: WeatherManager):
        self.weather_manager = weather_manager
        self.font = pygame.font.Font(None, 24)
        self.small_font = pygame.font.Font(None, 20)
        self.icon_size = 48
        self.icons = WeatherIcon(self.icon_size)
        
        # Colors
        self.BG_COLOR = (0, 0, 0, 180)
        self.TEXT_COLOR = (255, 255, 255)
        self.WARNING_COLOR = (255, 64, 64)
        
        # Accessibility
        self.show_detailed_text = True
        self.high_contrast = False
        
    def get_weather_warning(self, condition: WeatherCondition) -> Optional[str]:
        """Get warning message for dangerous weather conditions."""
        warnings = []
        
        if condition.type in {WeatherType.BLIZZARD, WeatherType.HEAVY_RAIN}:
            warnings.append("Extreme weather conditions")
        if condition.visibility < 1000:
            warnings.append("Very low visibility")
        if condition.road_grip < 0.4:
            warnings.append("Dangerous road conditions")
        if condition.wind_speed > 60:
            warnings.append("High wind warning")
            
        return " | ".join(warnings) if warnings else None
    
    def render(self, surface: pygame.Surface, position: Tuple[int, int]):
        """Render weather forecast UI."""
        # Create forecast panel
        width = 300
        height = 200 if self.show_detailed_text else 120
        panel = pygame.Surface((width, height), pygame.SRCALPHA)
        panel.fill(self.BG_COLOR)
        
        # Current weather
        current = self.weather_manager.weather_system.current_condition
        icon = self.icons.get_icon(current.type)
        panel.blit(icon, (10, 10))
        
        # Current weather text
        weather_text = f"{current.type.name.replace('_', ' ').title()}"
        text_surf = self.font.render(weather_text, True, self.TEXT_COLOR)
        panel.blit(text_surf, (70, 10))
        
        # Temperature and conditions
        temp_text = f"{current.temperature:.1f}°C"
        temp_surf = self.font.render(temp_text, True, self.TEXT_COLOR)
        panel.blit(temp_surf, (70, 35))
        
        # Weather warning if any
        warning = self.get_weather_warning(current)
        if warning:
            warning_surf = self.small_font.render(warning, True, self.WARNING_COLOR)
            panel.blit(warning_surf, (10, 70))
        
        if self.show_detailed_text:
            # Detailed conditions
            details = [
                f"Visibility: {current.visibility:.0f}m",
                f"Wind: {current.wind_speed:.1f} km/h",
                f"Road Grip: {current.road_grip:.2f}"
            ]
            
            y = 100
            for detail in details:
                detail_surf = self.small_font.render(detail, True, self.TEXT_COLOR)
                panel.blit(detail_surf, (10, y))
                y += 20
            
            # Weather duration
            weather_report = self.weather_manager.get_weather_report()
            duration_parts = weather_report.split('duration: ')
            if len(duration_parts) > 1:
                duration = duration_parts[1].split('\n')[0]
                duration_text = f"Expected duration: {duration}"
                duration_surf = self.small_font.render(duration_text, True, self.TEXT_COLOR)
                panel.blit(duration_surf, (10, y + 10))
        
        # Render panel to main surface
        surface.blit(panel, position)
    
    def handle_input(self, event: pygame.event.Event) -> bool:
        """Handle UI input events."""
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_F3:  # Toggle detailed view
                self.show_detailed_text = not self.show_detailed_text
                return True
            elif event.key == pygame.K_F4:  # Toggle high contrast
                self.high_contrast = not self.high_contrast
                return True
        return False
    
    def get_accessibility_text(self) -> str:
        """Get screen reader friendly weather description."""
        current = self.weather_manager.weather_system.current_condition
        warning = self.get_weather_warning(current)
        
        text = [
            f"Current weather is {current.type.name.replace('_', ' ')}.",
            f"Temperature is {current.temperature:.1f} degrees Celsius.",
            f"Visibility is {current.visibility:.0f} meters.",
            f"Wind speed is {current.wind_speed:.1f} kilometers per hour.",
            f"Road grip factor is {current.road_grip:.2f}."
        ]
        
        if warning:
            text.append(f"Warning: {warning}")
            
        return " ".join(text)
