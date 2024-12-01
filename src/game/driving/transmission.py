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
        
    def start_shift(self, target_gear: int) -> bool:
        """Start shifting to a new gear."""
        if self.state == GearState.SHIFTING:
            return False
            
        if 1 <= target_gear <= len(self.gear_ratios):
            self.target_gear = target_gear
            self.state = GearState.SHIFTING
            self.shift_timer = 0.0
            return True
        return False
    
    def update(self, dt: float, clutch: float) -> bool:
        """Update transmission state.
        Returns True if gear shift completed this update.
        """
        if self.state == GearState.SHIFTING:
            if clutch < 0.8:  # Need clutch mostly disengaged to shift
                return False
                
            self.shift_timer += dt
            if self.shift_timer >= self.shift_duration:
                self.complete_shift()
                return True
        return False
    
    def complete_shift(self):
        """Complete the gear shift."""
        if self.target_gear is not None:
            self.current_gear = self.target_gear
            self.target_gear = None
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
