from dataclasses import dataclass
from typing import Dict, List, Optional
import math

@dataclass
class EngineDef:
    max_hp: float
    max_torque: float
    rpm_range: tuple[int, int]  # (idle_rpm, max_rpm)
    optimal_rpm: int
    gear_ratios: List[float]
    
@dataclass
class TruckSpecs:
    mass: float  # kg
    drag_coefficient: float
    rolling_resistance: float
    wheel_radius: float  # meters
    brake_force: float
    engine: EngineDef

class TruckPhysics:
    def __init__(self, specs: TruckSpecs):
        self.specs = specs
        
        # Dynamic state
        self.velocity = 0.0  # m/s
        self.acceleration = 0.0  # m/s²
        self.current_gear = 1
        self.engine_rpm = specs.engine.rpm_range[0]  # Start at idle
        self.throttle = 0.0  # 0.0 to 1.0
        self.brake = 0.0  # 0.0 to 1.0
        self.clutch = 0.0  # 0.0 to 1.0 (0 = engaged, 1 = disengaged)
        
        # Vehicle systems state
        self.engine_temperature = 80.0  # Celsius
        self.brake_temperature = 20.0  # Celsius
        self.fuel_level = 100.0  # percentage
        self.tire_wear = [100.0] * 18  # percentage for each tire (typical 18-wheeler)
        
        # Warning states
        self.warnings = {
            'engine_temp': False,
            'brake_temp': False,
            'low_fuel': False,
            'tire_wear': False
        }
    
    def calculate_engine_force(self) -> float:
        """Calculate engine force based on current state."""
        if self.clutch == 1.0:  # Clutch fully disengaged
            return 0.0
            
        # Get torque for current RPM (simplified curve)
        rpm_percentage = (self.engine_rpm - self.specs.engine.rpm_range[0]) / (
            self.specs.engine.rpm_range[1] - self.specs.engine.rpm_range[0]
        )
        max_torque = self.specs.engine.max_torque
        
        # Simplified torque curve with peak at optimal RPM
        torque = max_torque * (1 - abs(rpm_percentage - 0.6))
        
        # Apply throttle and gear ratio
        gear_ratio = self.specs.engine.gear_ratios[self.current_gear - 1]
        drive_force = (
            torque * gear_ratio * self.throttle * (1 - self.clutch)
        ) / self.specs.wheel_radius
        
        return drive_force
    
    def calculate_resistance_forces(self) -> float:
        """Calculate total resistance forces."""
        # Air resistance
        air_resistance = (
            0.5 * 1.225 * self.specs.drag_coefficient * 
            self.velocity * abs(self.velocity)
        )
        
        # Rolling resistance
        rolling_resistance = (
            self.specs.mass * 9.81 * self.specs.rolling_resistance
        )
        
        # Brake force
        brake_force = self.specs.brake_force * self.brake
        
        return air_resistance + rolling_resistance + brake_force
    
    def update_engine_rpm(self):
        """Update engine RPM based on speed and gear."""
        if self.clutch == 1.0:  # Clutch disengaged
            # RPM falls toward idle
            rpm_change = (self.specs.engine.rpm_range[0] - self.engine_rpm) * 0.1
            self.engine_rpm = max(
                self.specs.engine.rpm_range[0],
                self.engine_rpm + rpm_change
            )
        else:
            # Calculate RPM from wheel speed and gear ratio
            gear_ratio = self.specs.engine.gear_ratios[self.current_gear - 1]
            wheel_rpm = self.velocity / (2 * math.pi * self.specs.wheel_radius) * 60
            self.engine_rpm = wheel_rpm * gear_ratio
            
            # Clamp RPM to valid range
            self.engine_rpm = min(
                max(self.engine_rpm, self.specs.engine.rpm_range[0]),
                self.specs.engine.rpm_range[1]
            )
    
    def update_temperatures(self, dt: float):
        """Update engine and brake temperatures."""
        # Engine temperature
        load_factor = self.throttle * (self.engine_rpm / self.specs.engine.rpm_range[1])
        temp_change = (load_factor * 50 - (self.engine_temperature - 80) * 0.1) * dt
        self.engine_temperature += temp_change
        
        # Brake temperature
        brake_load = self.brake * abs(self.velocity)
        brake_temp_change = (brake_load * 30 - (self.brake_temperature - 20) * 0.2) * dt
        self.brake_temperature += brake_temp_change
        
        # Update warning states
        self.warnings['engine_temp'] = self.engine_temperature > 100
        self.warnings['brake_temp'] = self.brake_temperature > 500
    
    def update_fuel(self, dt: float):
        """Update fuel consumption."""
        # Basic fuel consumption based on throttle and RPM
        load_factor = self.throttle * (self.engine_rpm / self.specs.engine.rpm_range[1])
        fuel_consumption = load_factor * 0.5 * dt  # percentage per second
        self.fuel_level = max(0.0, self.fuel_level - fuel_consumption)
        
        self.warnings['low_fuel'] = self.fuel_level < 10.0
    
    def update_tire_wear(self, dt: float):
        """Update tire wear based on driving conditions."""
        # Basic wear calculation
        base_wear = abs(self.velocity) * dt * 0.0001
        
        # Additional wear from harsh braking
        brake_wear = self.brake * abs(self.velocity) * dt * 0.0002
        
        # Apply wear to all tires
        for i in range(len(self.tire_wear)):
            self.tire_wear[i] = max(0.0, self.tire_wear[i] - (base_wear + brake_wear))
            
        # Update warning state
        self.warnings['tire_wear'] = any(wear < 20.0 for wear in self.tire_wear)
    
    def update(self, dt: float):
        """Update truck physics for one time step."""
        # Calculate forces
        drive_force = self.calculate_engine_force()
        resistance_force = self.calculate_resistance_forces()
        
        # Calculate acceleration
        net_force = drive_force - resistance_force
        self.acceleration = net_force / self.specs.mass
        
        # Update velocity with minimum of 0
        self.velocity = max(0.0, self.velocity + self.acceleration * dt)
        
        # Update engine and vehicle systems
        self.update_engine_rpm()
        self.update_temperatures(dt)
        self.update_fuel(dt)
        self.update_tire_wear(dt)
        
    def get_speed_kph(self) -> float:
        """Get current speed in kilometers per hour."""
        return self.velocity * 3.6
    
    def get_status(self) -> Dict:
        """Get current vehicle status."""
        return {
            'speed': self.get_speed_kph(),
            'rpm': self.engine_rpm,
            'gear': self.current_gear,
            'engine_temp': self.engine_temperature,
            'brake_temp': self.brake_temperature,
            'fuel': self.fuel_level,
            'tire_wear': min(self.tire_wear),
            'warnings': self.warnings
        }
