import pygame
import math
from typing import Dict, Optional, Tuple
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
    def __init__(self, screen: pygame.Surface, truck: TruckPhysics, transmission: Transmission):
        self.screen = screen
        self.truck = truck
        self.transmission = transmission
        
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
        
        self.speedometer = Gauge(
            screen,
            (screen_width - 150, screen_height - 100),
            80,
            0,
            140,  # max speed in kph
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
        
    def draw_gear_indicator(self):
        """Draw the current gear and shift state."""
        gear_state = self.transmission.get_state()
        current_gear = gear_state['gear']
        shift_state = gear_state['state']
        
        # Background
        gear_rect = pygame.Rect(
            self.screen.get_width() // 2 - 30,
            self.screen.get_height() - 100,
            60,
            60
        )
        pygame.draw.rect(self.screen, self.BLACK, gear_rect)
        pygame.draw.rect(self.screen, self.WHITE, gear_rect, 2)
        
        # Gear number
        color = self.YELLOW if shift_state == 'SHIFTING' else self.WHITE
        gear_text = self.large_font.render(str(current_gear), True, color)
        gear_text_rect = gear_text.get_rect(center=gear_rect.center)
        self.screen.blit(gear_text, gear_text_rect)
        
        # Shift progress if shifting
        if shift_state == 'SHIFTING':
            progress = gear_state['shifting_progress']
            progress_rect = pygame.Rect(
                gear_rect.x,
                gear_rect.bottom - 5,
                gear_rect.width * progress,
                5
            )
            pygame.draw.rect(self.screen, self.YELLOW, progress_rect)
    
    def draw_warning_indicators(self):
        """Draw warning indicators for vehicle systems."""
        warnings = self.truck.warnings
        
        for warning_type, rect in self.warning_icons.items():
            # Draw icon background
            color = self.RED if warnings[warning_type] else (50, 50, 50)
            pygame.draw.rect(self.screen, color, rect)
            pygame.draw.rect(self.screen, self.WHITE, rect, 1)
            
            # Draw icon symbol
            symbol = {
                'engine_temp': '°C',
                'brake_temp': 'B',
                'low_fuel': 'F',
                'tire_wear': 'T'
            }[warning_type]
            
            text = self.small_font.render(symbol, True, self.WHITE)
            text_rect = text.get_rect(center=rect.center)
            self.screen.blit(text, text_rect)
    
    def draw_system_status(self):
        """Draw detailed system status information."""
        status = self.truck.get_status()
        
        # Create status texts
        texts = [
            f"Engine: {status['engine_temp']:.0f}°C",
            f"Brakes: {status['brake_temp']:.0f}°C",
            f"Tires: {status['tire_wear']:.0f}%"
        ]
        
        # Draw status panel
        y = 60
        for text in texts:
            surface = self.small_font.render(text, True, self.WHITE)
            self.screen.blit(surface, (20, y))
            y += 25
    
    def render(self):
        """Render the complete HUD."""
        status = self.truck.get_status()
        
        # Draw gauges
        self.speedometer.draw(
            status['speed'],
            status['speed'] > 120  # Warning if speeding
        )
        
        self.tachometer.draw(
            status['rpm'],
            status['rpm'] > 2500  # Warning if over-revving
        )
        
        self.fuel_gauge.draw(
            status['fuel'],
            status['fuel'] < 10  # Warning if low fuel
        )
        
        # Draw gear indicator
        self.draw_gear_indicator()
        
        # Draw warning indicators
        self.draw_warning_indicators()
        
        # Draw system status
        self.draw_system_status()
        
        # Draw labels
        speed_label = self.medium_font.render("KPH", True, self.WHITE)
        rpm_label = self.medium_font.render("RPM", True, self.WHITE)
        fuel_label = self.medium_font.render("FUEL", True, self.WHITE)
        
        self.screen.blit(speed_label, (self.screen.get_width() - 150, self.screen.get_height() - 30))
        self.screen.blit(rpm_label, (150, self.screen.get_height() - 30))
        self.screen.blit(fuel_label, (self.screen.get_width() - 300, self.screen.get_height() - 30))
