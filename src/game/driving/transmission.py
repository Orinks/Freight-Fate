from enum import Enum
from typing import Optional

class GearState(Enum):
    NEUTRAL = 0
    SHIFTING = 1
    ENGAGED = 2

class Transmission:
    def __init__(self, gear_ratios: list[float]):
        self.gear_ratios = gear_ratios
        self.current_gear = 1
        self.state = GearState.ENGAGED
        self.shift_timer = 0.0
        self.shift_duration = 0.5  # seconds to complete gear shift
        self.target_gear: Optional[int] = None
        self.clutch_position = 0.0  # Add clutch position tracking
        
    def start_shift(self, target_gear: int) -> bool:
        """Start shifting to a new gear."""
        if self.state == GearState.SHIFTING:
            return False
            
        if 1 <= target_gear <= len(self.gear_ratios):
            # Only shift if clutch is pressed enough
            if self.clutch_position > 0.8:
                self.target_gear = target_gear
                self.state = GearState.SHIFTING
                self.shift_timer = 0.0
                print(f"Shifting to gear {target_gear}")
                return True
            else:
                print("Cannot shift - clutch not pressed enough")
                return False
        return False
    
    def update(self, dt: float, clutch: float) -> bool:
        """Update transmission state.
        Returns True if gear shift completed this update.
        """
        self.clutch_position = clutch  # Update clutch position
        
        if self.state == GearState.SHIFTING:
            if clutch < 0.8:  # Need clutch mostly disengaged to shift
                print("Cannot complete shift - clutch not pressed enough")
                self.state = GearState.ENGAGED  # Cancel shift if clutch released too early
                self.shift_timer = 0.0
                return False
                
            self.shift_timer += dt
            if self.shift_timer >= self.shift_duration:
                self.complete_shift()
                print(f"Shift completed - now in gear {self.current_gear}")
                return True
        return False
    
    def complete_shift(self):
        """Complete the gear shift."""
        if self.target_gear is not None:
            self.current_gear = self.target_gear
            self.target_gear = None
            # Play gear shift sound
            if hasattr(self, 'sound_manager') and self.sound_manager:
                self.sound_manager.play_gear_shift()
        self.state = GearState.ENGAGED
        self.shift_timer = 0.0
    
    def get_current_ratio(self) -> float:
        """Get the current gear ratio."""
        return self.gear_ratios[self.current_gear - 1]
    
    def get_state(self) -> dict:
        """Get current transmission state."""
        return {
            'gear': self.current_gear,
            'state': self.state.name,
            'shifting_progress': (
                self.shift_timer / self.shift_duration 
                if self.state == GearState.SHIFTING 
                else 0.0
            )
        }
