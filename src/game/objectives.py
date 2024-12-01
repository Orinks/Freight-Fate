import random
from typing import Dict, List, Optional
from datetime import datetime, timedelta

class Objective:
    def __init__(self, name: str, description: str, reward: float):
        self.name = name
        self.description = description
        self.reward = reward
        self.completed = False
        self.failed = False

class RouteChallenge:
    def __init__(self, name: str, description: str, difficulty: int):
        self.name = name
        self.description = description
        self.difficulty = difficulty  # 1-5 scale
        self.active = False
        self.completed = False

class ObjectiveGenerator:
    ROUTE_CHALLENGES = {
        "Weather": [
            {"name": "Heavy Rain", "description": "Drive carefully through heavy rainfall", "difficulty": 2},
            {"name": "Snow Storm", "description": "Navigate through snowy conditions", "difficulty": 4},
            {"name": "Dense Fog", "description": "Maintain safety in low visibility", "difficulty": 3},
            {"name": "High Winds", "description": "Handle strong crosswinds", "difficulty": 3}
        ],
        "Traffic": [
            {"name": "Rush Hour", "description": "Navigate through heavy city traffic", "difficulty": 2},
            {"name": "Construction Zone", "description": "Carefully pass through road work", "difficulty": 3},
            {"name": "Highway Merger", "description": "Handle heavy merging traffic", "difficulty": 2},
            {"name": "Accident Slowdown", "description": "Navigate through accident-related delays", "difficulty": 3}
        ],
        "Road": [
            {"name": "Mountain Pass", "description": "Navigate steep mountain grades", "difficulty": 4},
            {"name": "Tight Curves", "description": "Handle winding road sections", "difficulty": 3},
            {"name": "Bridge Crossing", "description": "Cross a major bridge in challenging conditions", "difficulty": 2},
            {"name": "Urban Navigation", "description": "Navigate through tight city streets", "difficulty": 3}
        ]
    }

    BONUS_OBJECTIVES = [
        {"name": "Fuel Efficiency", "description": "Maintain high fuel efficiency", "base_reward": 200},
        {"name": "Perfect Schedule", "description": "Arrive exactly on time", "base_reward": 300},
        {"name": "Cargo Care", "description": "Deliver cargo with minimal movement", "base_reward": 250},
        {"name": "Safe Driver", "description": "Maintain safe following distance", "base_reward": 200},
        {"name": "Speed Control", "description": "Stay within speed limits", "base_reward": 150}
    ]

    def __init__(self, route_data: Dict):
        self.route_data = route_data

    def generate_route_challenges(self, route: str, season: str, time_of_day: str) -> List[RouteChallenge]:
        challenges = []
        
        # Generate weather challenges based on season
        if season == "winter":
            weather_weights = {"Snow Storm": 0.4, "Heavy Rain": 0.2, "Dense Fog": 0.2, "High Winds": 0.2}
        elif season == "spring":
            weather_weights = {"Heavy Rain": 0.4, "Dense Fog": 0.3, "High Winds": 0.3}
        elif season == "summer":
            weather_weights = {"Heavy Rain": 0.3, "Dense Fog": 0.2, "High Winds": 0.5}
        else:  # fall
            weather_weights = {"Heavy Rain": 0.3, "Dense Fog": 0.4, "High Winds": 0.3}

        # Add weather challenge
        weather_type = random.choices(list(weather_weights.keys()), 
                                    weights=list(weather_weights.values()))[0]
        for challenge in self.ROUTE_CHALLENGES["Weather"]:
            if challenge["name"] == weather_type:
                challenges.append(RouteChallenge(**challenge))

        # Add traffic challenge based on time of day
        if time_of_day in ["morning", "evening"]:
            challenges.append(RouteChallenge(**self.ROUTE_CHALLENGES["Traffic"][0]))  # Rush Hour
        else:
            challenges.append(RouteChallenge(**random.choice(self.ROUTE_CHALLENGES["Traffic"][1:])))

        # Add road challenge based on route terrain
        terrain_challenges = {
            "mountains": "Mountain Pass",
            "urban": "Urban Navigation",
            "coastal": "Bridge Crossing",
            "rural": "Tight Curves"
        }
        
        for terrain_type, challenge_name in terrain_challenges.items():
            if terrain_type in str(self.route_data.get("terrain", [])):
                for challenge in self.ROUTE_CHALLENGES["Road"]:
                    if challenge["name"] == challenge_name:
                        challenges.append(RouteChallenge(**challenge))
                        break

        return challenges

    def generate_bonus_objectives(self, route_length: float, cargo_value: float) -> List[Objective]:
        objectives = []
        
        # Scale rewards based on route length and cargo value
        distance_multiplier = route_length / 100  # Base multiplier for every 100 miles
        value_multiplier = 1 + (cargo_value / 100000)  # Increase multiplier for valuable cargo
        
        for obj_template in self.BONUS_OBJECTIVES:
            reward = obj_template["base_reward"] * distance_multiplier * value_multiplier
            objectives.append(
                Objective(
                    name=obj_template["name"],
                    description=obj_template["description"],
                    reward=round(reward, 2)
                )
            )
        
        return objectives

class RouteProgress:
    def __init__(self, job, route_challenges: List[RouteChallenge], bonus_objectives: List[Objective]):
        self.job = job
        self.route_challenges = route_challenges
        self.bonus_objectives = bonus_objectives
        self.start_time = None
        self.current_position = None
        self.distance_covered = 0.0
        self.fuel_used = 0.0
        self.rest_stops_taken = []
        self.violations = []  # Speed, safety, or other violations
        
    def start_route(self):
        self.start_time = datetime.now()
        self.current_position = self.job.start_city
        
    def update_progress(self, position, distance_covered, fuel_used):
        self.current_position = position
        self.distance_covered = distance_covered
        self.fuel_used = fuel_used
        
    def add_violation(self, violation_type: str, description: str):
        self.violations.append({
            "type": violation_type,
            "description": description,
            "time": datetime.now()
        })
        
    def add_rest_stop(self, stop_name: str, duration: timedelta):
        self.rest_stops_taken.append({
            "name": stop_name,
            "time": datetime.now(),
            "duration": duration
        })
        
    def calculate_score(self) -> Dict:
        base_score = 1000
        
        # Deduct points for violations
        violation_penalty = len(self.violations) * 100
        
        # Add points for completed challenges
        challenge_bonus = sum(200 for challenge in self.route_challenges if challenge.completed)
        
        # Add points for completed objectives
        objective_bonus = sum(obj.reward for obj in self.bonus_objectives if obj.completed)
        
        return {
            "base_score": base_score,
            "violation_penalty": violation_penalty,
            "challenge_bonus": challenge_bonus,
            "objective_bonus": objective_bonus,
            "final_score": base_score - violation_penalty + challenge_bonus + objective_bonus
        }
