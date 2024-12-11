"""Game settings and configuration management."""
import os
import json

class Settings:
    def __init__(self):
        self.use_imperial = True  # Default to imperial for US setting
        self.settings_file = self._get_settings_path()
        self.is_dirty = False
        self.load_settings()
        
    def _get_settings_path(self):
        """Get the path to the settings file."""
        # Get the absolute path to the game directory
        current_file = os.path.abspath(__file__)
        src_dir = os.path.dirname(os.path.dirname(current_file))
        project_root = os.path.dirname(src_dir)
        
        # Create settings directory if it doesn't exist
        settings_dir = os.path.join(project_root, 'data', 'settings')
        os.makedirs(settings_dir, exist_ok=True)
        
        return os.path.join(settings_dir, 'game_settings.json')
        
    def load_settings(self):
        """Load settings from file."""
        try:
            if os.path.exists(self.settings_file):
                with open(self.settings_file, 'r') as f:
                    data = json.load(f)
                    self.use_imperial = data.get('use_imperial', True)
                print(f"Settings loaded: Using {'imperial' if self.use_imperial else 'metric'} units")
        except Exception as e:
            print(f"Error loading settings: {e}")
        
    def save_settings(self):
        """Save settings to file."""
        try:
            data = {
                'use_imperial': self.use_imperial
            }
            with open(self.settings_file, 'w') as f:
                json.dump(data, f, indent=4)
            print(f"Settings saved: Using {'imperial' if self.use_imperial else 'metric'} units")
        except Exception as e:
            print(f"Error saving settings: {e}")
        
    def toggle_units(self):
        """Toggle between imperial and metric units."""
        self.use_imperial = not self.use_imperial
        self.is_dirty = True
        
    def get_speed_unit(self):
        """Get the current speed unit."""
        return "mph" if self.use_imperial else "km/h"
        
    def get_distance_unit(self):
        """Get the current distance unit."""
        return "miles" if self.use_imperial else "km"
        
    def get_weight_unit(self):
        """Get the current weight unit."""
        return "lbs" if self.use_imperial else "kg"
        
    def convert_speed(self, speed_kph):
        """Convert speed from km/h to current unit."""
        if self.use_imperial:
            return speed_kph * 0.621371  # Convert to mph
        return speed_kph
        
    def convert_distance(self, distance_km):
        """Convert distance from km to current unit."""
        if self.use_imperial:
            return distance_km * 0.621371  # Convert to miles
        return distance_km
        
    def convert_weight(self, weight_kg):
        """Convert weight from kg to current unit."""
        if self.use_imperial:
            return weight_kg * 2.20462  # Convert to pounds
        return weight_kg
        
    def format_speed(self, speed_kph, include_unit=True):
        """Format speed with appropriate unit."""
        converted = self.convert_speed(speed_kph)
        if include_unit:
            return f"{converted:.1f} {self.get_speed_unit()}"
        return f"{converted:.1f}"
        
    def format_distance(self, distance_km, include_unit=True):
        """Format distance with appropriate unit."""
        converted = self.convert_distance(distance_km)
        if include_unit:
            return f"{converted:.1f} {self.get_distance_unit()}"
        return f"{converted:.1f}"
        
    def format_weight(self, weight_kg, include_unit=True):
        """Format weight with appropriate unit."""
        converted = self.convert_weight(weight_kg)
        if include_unit:
            return f"{converted:.0f} {self.get_weight_unit()}"
        return f"{converted:.0f}"
