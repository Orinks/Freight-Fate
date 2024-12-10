import pygame
from typing import Optional
from ..settings import Settings
from .vehicle import TruckPhysics
from .transmission import Transmission

class DrivingInputHandler:
    def __init__(self, truck: TruckPhysics, transmission: Transmission):
        self.truck = truck
        self.transmission = transmission
        self.settings = None  # Will be set by DrivingState
        
        # Input state
        self.throttle_input = 0.0
        self.brake_input = 0.0
        self.clutch_input = 0.0
        self.steering = 0.0
        
        # Key state tracking
        self.shift_keys_held = set()
        
    def set_settings(self, settings):
        """Set the settings instance for unit conversion."""
        self.settings = settings
        
    def handle_event(self, event: pygame.event.Event) -> Optional[str]:
        """Handle a single input event."""
        if event.type == pygame.KEYDOWN:
            # Gear shifting
            if event.key in range(pygame.K_1, pygame.K_9):
                gear = event.key - pygame.K_1 + 1
                if gear <= len(self.transmission.gear_ratios):
                    self.shift_keys_held.add(gear)
                    
            # Other controls
            elif event.key == pygame.K_SPACE:
                self.brake_input = 1.0
            elif event.key == pygame.K_LSHIFT:
                self.clutch_input = 1.0
            elif event.key == pygame.K_u and self.settings:  # Add unit toggle
                self.settings.toggle_units()
                
        elif event.type == pygame.KEYUP:
            if event.key in range(pygame.K_1, pygame.K_9):
                gear = event.key - pygame.K_1 + 1
                self.shift_keys_held.discard(gear)
            elif event.key == pygame.K_SPACE:
                self.brake_input = 0.0
            elif event.key == pygame.K_LSHIFT:
                self.clutch_input = 0.0
                
        return None
    
    def update(self, dt: float):
        """Update continuous inputs."""
        keys = pygame.key.get_pressed()
        
        # Throttle (W/S)
        if keys[pygame.K_w]:
            self.throttle_input = min(1.0, self.throttle_input + dt * 2)
        elif keys[pygame.K_s]:
            self.throttle_input = max(0.0, self.throttle_input - dt * 2)
        
        # Steering (A/D)
        if keys[pygame.K_a]:
            self.steering = max(-1.0, self.steering - dt * 2)
        elif keys[pygame.K_d]:
            self.steering = min(1.0, self.steering + dt * 2)
        else:
            # Return to center
            if self.steering > 0:
                self.steering = max(0.0, self.steering - dt)
            else:
                self.steering = min(0.0, self.steering + dt)
        
        # Try to shift if key held
        if self.shift_keys_held and self.clutch_input > 0.8:
            target_gear = min(self.shift_keys_held)
            self.transmission.start_shift(target_gear)
        
        # Update vehicle controls
        self.truck.throttle = self.throttle_input
        self.truck.brake = self.brake_input
        self.truck.clutch = self.clutch_input
        
        # Update transmission
        self.transmission.update(dt, self.clutch_input)
    
    def get_input_state(self) -> dict:
        """Get current input state."""
        return {
            'throttle': self.throttle_input,
            'brake': self.brake_input,
            'clutch': self.clutch_input,
            'steering': self.steering,
            'shift_keys': list(self.shift_keys_held)
        }
