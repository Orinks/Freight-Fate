import random
from datetime import datetime, timedelta
from typing import Dict, List, Optional

class Cargo:
    def __init__(self, name: str, weight: float, value: float, fragile: bool = False, hazardous: bool = False):
        self.name = name
        self.weight = weight  # in tons
        self.value = value   # in dollars
        self.fragile = fragile
        self.hazardous = hazardous

class Job:
    def __init__(self, 
                 cargo: Cargo,
                 start_city: str,
                 end_city: str,
                 deadline_hours: int,
                 base_pay: float,
                 bonus_pay: float = 0.0,
                 required_license: str = "Class A CDL"):
        self.cargo = cargo
        self.start_city = start_city
        self.end_city = end_city
        self.creation_time = datetime.now()
        self.deadline = self.creation_time + timedelta(hours=deadline_hours)
        self.base_pay = base_pay
        self.bonus_pay = bonus_pay
        self.required_license = required_license
        self.active = False
        self.completed = False
        
    def time_remaining(self) -> timedelta:
        return self.deadline - datetime.now()
    
    def is_expired(self) -> bool:
        return datetime.now() > self.deadline
    
    def calculate_pay(self, delivery_time: datetime) -> float:
        if delivery_time > self.deadline:
            # Penalty for late delivery (10% per hour, up to 50%)
            hours_late = (delivery_time - self.deadline).total_seconds() / 3600
            penalty = min(0.5, hours_late * 0.1)
            return self.base_pay * (1 - penalty)
        else:
            # Bonus for early delivery
            hours_early = (self.deadline - delivery_time).total_seconds() / 3600
            bonus_multiplier = min(0.2, hours_early * 0.02)  # Up to 20% bonus
            return self.base_pay + (self.bonus_pay * bonus_multiplier)

class JobGenerator:
    CARGO_TYPES = {
        "General Freight": {"weight": (5, 20), "value": (10000, 50000), "fragile": False, "hazardous": False},
        "Electronics": {"weight": (2, 10), "value": (50000, 200000), "fragile": True, "hazardous": False},
        "Fresh Produce": {"weight": (10, 25), "value": (20000, 60000), "fragile": True, "hazardous": False},
        "Construction Materials": {"weight": (15, 30), "value": (15000, 45000), "fragile": False, "hazardous": False},
        "Hazardous Materials": {"weight": (5, 15), "value": (40000, 100000), "fragile": False, "hazardous": True},
        "Vehicles": {"weight": (10, 20), "value": (100000, 300000), "fragile": True, "hazardous": False},
        "Livestock": {"weight": (10, 25), "value": (50000, 150000), "fragile": True, "hazardous": False}
    }

    def __init__(self, cities_data: Dict):
        self.cities_data = cities_data
        
    def generate_cargo(self, cargo_type: Optional[str] = None) -> Cargo:
        if cargo_type is None:
            cargo_type = random.choice(list(self.CARGO_TYPES.keys()))
            
        cargo_info = self.CARGO_TYPES[cargo_type]
        weight = random.uniform(*cargo_info["weight"])
        value = random.uniform(*cargo_info["value"])
        
        return Cargo(
            name=cargo_type,
            weight=weight,
            value=value,
            fragile=cargo_info["fragile"],
            hazardous=cargo_info["hazardous"]
        )
    
    def calculate_base_pay(self, distance: float, cargo: Cargo) -> float:
        # Base rate of $2 per mile
        base_rate = 2.0
        
        # Adjust for cargo value and special handling
        value_multiplier = 1.0 + (cargo.value / 1000000)  # Increase rate for valuable cargo
        special_handling = 1.0
        if cargo.fragile:
            special_handling += 0.2  # 20% extra for fragile cargo
        if cargo.hazardous:
            special_handling += 0.3  # 30% extra for hazardous cargo
            
        return distance * base_rate * value_multiplier * special_handling
    
    def generate_job(self, player_level: int = 1) -> Job:
        # Select random start and end cities
        cities = list(self.cities_data.keys())
        start_city = random.choice(cities)
        end_city = random.choice([city for city in cities if city != start_city])
        
        # Calculate straight-line distance (this should be replaced with actual route distance)
        start_coords = (self.cities_data[start_city]["lat"], self.cities_data[start_city]["lon"])
        end_coords = (self.cities_data[end_city]["lat"], self.cities_data[end_city]["lon"])
        
        # Generate random cargo based on player level
        cargo_types = list(self.CARGO_TYPES.keys())
        if player_level < 3:
            # New players get safer cargo
            cargo_types = [ct for ct in cargo_types if not self.CARGO_TYPES[ct]["hazardous"]]
        
        cargo = self.generate_cargo(random.choice(cargo_types))
        
        # Calculate deadline based on distance and cargo type
        distance = 100  # This should be replaced with actual route distance
        base_speed = 55  # mph
        time_multiplier = 1.2  # Add 20% to theoretical minimum time
        deadline_hours = int((distance / base_speed) * time_multiplier)
        
        # Calculate pay
        base_pay = self.calculate_base_pay(distance, cargo)
        bonus_pay = base_pay * 0.2  # 20% potential bonus
        
        # Determine required license
        required_license = "Class A CDL"
        if cargo.hazardous:
            required_license = "Class A CDL-H"  # Hazmat endorsement
        
        return Job(
            cargo=cargo,
            start_city=start_city,
            end_city=end_city,
            deadline_hours=deadline_hours,
            base_pay=base_pay,
            bonus_pay=bonus_pay,
            required_license=required_license
        )
    
    def generate_available_jobs(self, current_city: str, player_level: int = 1, num_jobs: int = 3) -> List[Job]:
        """Generate a list of available jobs from the current city."""
        jobs = []
        for _ in range(num_jobs):
            job = self.generate_job(player_level)
            while job.start_city != current_city:
                job = self.generate_job(player_level)
            jobs.append(job)
        return jobs
