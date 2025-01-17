import pandas as pd
import numpy as np
import json
import os
from typing import Dict, List, Optional

class Economy:
    def __init__(self):
        self.data_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'data', 'economy.json')
        self.load_economic_data()
        
    def load_economic_data(self):
        """Load economic data from JSON file. If file doesn't exist, create default data."""
        try:
            with open(self.data_path, 'r') as f:
                self.economic_data = json.load(f)
        except FileNotFoundError:
            # Create default economic data
            self.economic_data = {
                'regions': {
                    'Texas': {'fuel_price': 2.50, 'demand_multiplier': 1.0},
                    'California': {'fuel_price': 3.75, 'demand_multiplier': 1.2},
                    'New York': {'fuel_price': 3.25, 'demand_multiplier': 1.1},
                    'Florida': {'fuel_price': 2.75, 'demand_multiplier': 0.9}
                },
                'goods': {
                    'electronics': {'base_price': 1000, 'volatility': 0.2},
                    'furniture': {'base_price': 500, 'volatility': 0.1},
                    'food': {'base_price': 200, 'volatility': 0.3},
                    'construction': {'base_price': 800, 'volatility': 0.15}
                }
            }
            self.save_economic_data()
    
    def save_economic_data(self):
        """Save current economic data to JSON file."""
        with open(self.data_path, 'w') as f:
            json.dump(self.economic_data, f, indent=4)
    
    def get_fuel_price(self, region: str) -> float:
        """Get current fuel price for a specific region."""
        return self.economic_data['regions'].get(region, {'fuel_price': 3.00})['fuel_price']
    
    def get_goods_price(self, good: str, region: str) -> float:
        """Calculate current price for goods in a specific region."""
        if good not in self.economic_data['goods']:
            return 0.0
            
        base_price = self.economic_data['goods'][good]['base_price']
        volatility = self.economic_data['goods'][good]['volatility']
        demand_multiplier = self.economic_data['regions'].get(region, {'demand_multiplier': 1.0})['demand_multiplier']
        
        # Add some randomness based on volatility
        random_factor = np.random.normal(1, volatility)
        price = base_price * demand_multiplier * random_factor
        
        return max(price, base_price * 0.5)  # Ensure price doesn't go too low
    
    def update_prices(self):
        """Update prices based on supply and demand."""
        for region in self.economic_data['regions']:
            # Slightly adjust demand multiplier
            current_multiplier = self.economic_data['regions'][region]['demand_multiplier']
            adjustment = np.random.normal(0, 0.1)  # Small random adjustment
            new_multiplier = max(0.5, min(2.0, current_multiplier + adjustment))  # Keep between 0.5 and 2.0
            self.economic_data['regions'][region]['demand_multiplier'] = new_multiplier
            
            # Update fuel prices with some randomness
            current_price = self.economic_data['regions'][region]['fuel_price']
            price_adjustment = np.random.normal(0, 0.1)  # Small random adjustment
            new_price = max(2.0, min(5.0, current_price + price_adjustment))  # Keep between $2.00 and $5.00
            self.economic_data['regions'][region]['fuel_price'] = new_price
        
        self.save_economic_data()
    
    def get_market_report(self) -> Dict[str, List[Dict]]:
        """Generate a market report showing highest and lowest prices for goods."""
        report = {'highest_prices': [], 'lowest_prices': []}
        
        for good in self.economic_data['goods']:
            prices = [(region, self.get_goods_price(good, region)) 
                     for region in self.economic_data['regions']]
            
            # Sort by price
            prices.sort(key=lambda x: x[1])
            
            # Add lowest and highest prices to report
            report['lowest_prices'].append({
                'good': good,
                'region': prices[0][0],
                'price': prices[0][1]
            })
            report['highest_prices'].append({
                'good': good,
                'region': prices[-1][0],
                'price': prices[-1][1]
            })
        
        return report
