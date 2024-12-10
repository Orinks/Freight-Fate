import pygame
import math
from typing import Dict, Optional, Tuple
from ..settings import Settings
from .vehicle import TruckPhysics
from .transmission import Transmission, GearState

class Gauge:
    def __init__(
        self, 
        surface: pygame.Surface,
        center: Tuple[int, int],
        radius: int,
        min_value: float,
        max_value: float,
        start_angle: float = -225,
        end_angle: float = 45,
        color: Tuple[int, int, int] = (255, 255, 255),
        warning_color: Tuple[int, int, int] = (255, 0, 0)
    ):
        self.surface = surface
        self.center = center
        self.radius = radius
        self.min_value = min_value
        self.max_value = max_value
        self.start_angle = start_angle
        self.end_angle = end_angle
        self.color = color
        self.warning_color = warning_color
        self.font = pygame.font.Font(None, 24)
        
    def draw(self, value: float, warning: bool = False):
        """Draw the gauge with current value."""
        # Draw background arc
        pygame.draw.arc(
            self.surface,
            (128, 128, 128),
            (
                self.center[0] - self.radius,
                self.center[1] - self.radius,
                self.radius * 2,
                self.radius * 2
            ),
            math.radians(self.start_angle),
            math.radians(self.end_angle),
            2
        )
        
        # Calculate value angle
        value_range = self.max_value - self.min_value
        angle_range = self.end_angle - self.start_angle
        value_angle = self.start_angle + (
            (value - self.min_value) / value_range * angle_range
        )
        
        # Draw value arc
        color = self.warning_color if warning else self.color
        pygame.draw.arc(
            self.surface,
            color,
            (
                self.center[0] - self.radius,
                self.center[1] - self.radius,
                self.radius * 2,
                self.radius * 2
            ),
            math.radians(self.start_angle),
            math.radians(value_angle),
            3
        )
        
        # Draw value text
        text = self.font.render(f"{value:.0f}", True, color)
        text_rect = text.get_rect(center=(
            self.center[0],
            self.center[1] + self.radius // 2
        ))
        self.surface.blit(text, text_rect)

class DrivingHUD:
    def __init__(self, screen: pygame.Surface, truck: TruckPhysics, transmission: Transmission, settings: Settings):
        self.screen = screen
        self.truck = truck
        self.transmission = transmission
        self.settings = settings
        
        # Colors
        self.WHITE = (255, 255, 255)
        self.BLACK = (0, 0, 0)
        self.RED = (255, 0, 0)
        self.YELLOW = (255, 255, 0)
        self.GREEN = (0, 255, 0)
        
        # Fonts
        self.large_font = pygame.font.Font(None, 48)
        self.medium_font = pygame.font.Font(None, 32)
        self.small_font = pygame.font.Font(None, 24)
        
        # Create gauges
        screen_width = screen.get_width()
        screen_height = screen.get_height()
        
        # Set max speed based on units (140 kph = ~87 mph)
        max_speed = 87 if self.settings.use_imperial else 140
        
        self.speedometer = Gauge(
            screen,
            (screen_width - 150, screen_height - 100),
            80,
            0,
            max_speed,  # max speed in current units
            color=self.GREEN
        )
        
        self.tachometer = Gauge(
            screen,
            (150, screen_height - 100),
            80,
            0,
            3000,  # max RPM
            color=self.YELLOW,
            warning_color=self.RED
        )
        
        self.fuel_gauge = Gauge(
            screen,
            (screen_width - 300, screen_height - 100),
            60,
            0,
            100,  # percentage
            -180,
            0,
            color=self.WHITE,
            warning_color=self.RED
        )
        
        # Warning icons
        self.warning_icons = {
            'engine_temp': pygame.Rect(20, 20, 30, 30),
            'brake_temp': pygame.Rect(60, 20, 30, 30),
            'low_fuel': pygame.Rect(100, 20, 30, 30),
            'tire_wear': pygame.Rect(140, 20, 30, 30)
        }
        
    def update(self, dt):
        """Update HUD state.
        
        Args:
            dt: Time delta since last update in seconds
        """
        # Update gauges
        self.speedometer.draw(self.settings.convert_speed(self.truck.get_speed_kph()))
        self.tachometer.draw(self.truck.engine_rpm, self.truck.engine_rpm > self.truck.specs.engine.rpm_range[1])
        self.fuel_gauge.draw(self.truck.fuel_level, self.truck.fuel_level < 20)
        
    def draw_gear_indicator(self):
        """Draw the current gear and shift state."""
        gear_text = str(self.transmission.current_gear) if self.transmission.current_gear > 0 else "N"
        if self.transmission.state == GearState.SHIFTING:
            gear_text += "..."
            
        gear_surface = self.large_font.render(gear_text, True, self.WHITE)
        gear_rect = gear_surface.get_rect(center=(self.screen.get_width() // 2, self.screen.get_height() - 100))
        self.screen.blit(gear_surface, gear_rect)
        
    def draw_warning_indicators(self):
        """Draw warning indicators for vehicle systems."""
        for name, rect in self.warning_icons.items():
            pygame.draw.rect(self.screen, self.RED if self.truck.warnings[name] else self.GREEN, rect)
            
    def draw_system_status(self):
        """Draw detailed system status information."""
        # Convert speed to current units
        speed = self.settings.convert_speed(self.truck.get_speed_kph())
        speed_unit = self.settings.get_speed_unit()
        
        # Render speed
        speed_text = f"{speed:.1f} {speed_unit}"
        speed_surface = self.medium_font.render(speed_text, True, self.WHITE)
        self.screen.blit(speed_surface, (self.screen.get_width() - 200, self.screen.get_height() - 150))
        
        # Render RPM
        rpm_text = f"{self.truck.engine_rpm:.0f} RPM"
        rpm_surface = self.medium_font.render(rpm_text, True, self.WHITE)
        self.screen.blit(rpm_surface, (100, self.screen.get_height() - 150))
        
        # Render fuel level
        fuel_text = f"Fuel: {self.truck.fuel_level:.0f}%"
        fuel_surface = self.small_font.render(fuel_text, True, self.WHITE)
        self.screen.blit(fuel_surface, (self.screen.get_width() - 350, self.screen.get_height() - 150))
        
    def render(self):
        """Render the complete HUD."""
        # Draw gauges with converted values
        speed = self.settings.convert_speed(self.truck.get_speed_kph())
        speed_text = self.settings.format_speed(speed)
        speed_surface = self.large_font.render(speed_text, True, self.WHITE)
        speed_rect = speed_surface.get_rect(center=(self.screen.get_width() // 2, self.screen.get_height() - 50))
        self.screen.blit(speed_surface, speed_rect)
        
        self.speedometer.draw(speed)
        self.tachometer.draw(self.truck.engine_rpm, self.truck.engine_rpm > self.truck.specs.engine.rpm_range[1])
        self.fuel_gauge.draw(self.truck.fuel_level, self.truck.fuel_level < 20)
        
        self.draw_gear_indicator()
        self.draw_warning_indicators()
        self.draw_system_status()
