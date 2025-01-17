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
        
        # Auto transmission state
        self.last_auto_shift_time = 0.0
        self.auto_shift_cooldown = 0.5  # Seconds between auto shifts
        
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
                    if self.clutch_input > 0.8:  # Try to shift immediately if clutch is pressed
                        self.transmission.start_shift(gear)
                    
            # Other controls
            elif event.key == pygame.K_SPACE:
                self.brake_input = 1.0
            elif event.key == pygame.K_LSHIFT:
                self.clutch_input = 1.0
                print(f"Clutch pressed - {self.clutch_input}")
            elif event.key == pygame.K_w:
                self.throttle_input = 1.0
                print(f"W pressed - Setting throttle to {self.throttle_input}")
                # Play rev sound on throttle press
                if self.truck and self.truck.sound_manager:
                    self.truck.sound_manager.play_engine_rev(self.truck.engine_rpm)
            elif event.key == pygame.K_s:
                self.brake_input = 1.0
                # Play brake sound when braking
                if self.truck and self.truck.sound_manager:
                    self.truck.sound_manager.play_brake()
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
            elif event.key == pygame.K_w:
                self.throttle_input = 0.0
                print(f"W released - Setting throttle to {self.throttle_input}")
            elif event.key == pygame.K_s:
                self.brake_input = 0.0
                
        return None
    
    def handle_auto_transmission(self, dt: float):
        """Handle automatic gear shifts based on RPM."""
        if not self.settings or not self.settings.auto_transmission:
            return
            
        # Auto-manage clutch
        if self.brake_input > 0.8:  # Heavy braking
            self.clutch_input = 1.0  # Disengage clutch
        else:
            self.clutch_input = 0.0  # Keep clutch engaged
            
        current_time = pygame.time.get_ticks() / 1000.0
        if current_time - self.last_auto_shift_time < self.auto_shift_cooldown:
            return
            
        # Get current RPM and gear
        rpm = self.truck.engine_rpm
        current_gear = self.transmission.current_gear
        max_rpm = self.truck.specs.engine.rpm_range[1]
        min_rpm = self.truck.specs.engine.rpm_range[0]
        
        # Shift up if RPM too high
        if rpm > max_rpm * 0.8 and current_gear < len(self.transmission.gear_ratios):
            self.clutch_input = 1.0
            self.transmission.start_shift(current_gear + 1)
            self.last_auto_shift_time = current_time
            
        # Shift down if RPM too low
        elif rpm < min_rpm * 1.5 and current_gear > 1:
            self.clutch_input = 1.0
            self.transmission.start_shift(current_gear - 1)
            self.last_auto_shift_time = current_time

    def update(self, dt: float):
        """Update continuous inputs."""
        keys = pygame.key.get_pressed()
        
        # Throttle (W/S)
        if keys[pygame.K_w]:
            self.throttle_input = min(1.0, self.throttle_input + dt * 2)
        elif keys[pygame.K_s]:
            self.throttle_input = max(0.0, self.throttle_input - dt * 2)
        else:
            if self.throttle_input > 0:
                self.throttle_input = max(0.0, self.throttle_input - dt * 2)
            else:
                self.throttle_input = min(0.0, self.throttle_input + dt * 2)
        
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
        
        # Only handle manual transmission inputs if auto is off
        if not self.settings or not self.settings.auto_transmission:
            # Handle manual clutch and gear shifting
            if self.shift_keys_held:
                target_gear = min(self.shift_keys_held)
                print(f"Attempting to shift to gear {target_gear}, clutch: {self.clutch_input}")
                self.transmission.start_shift(target_gear)
        else:
            # Handle automatic transmission
            self.handle_auto_transmission(dt)
        
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
