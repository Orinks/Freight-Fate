class Truck:
    def __init__(self):
        self.fuel = 100.0
        self.speed = 0.0
        self.cargo = None
        self.position = None
        self.maintenance_level = 100.0

    def update_fuel(self, distance_traveled):
        """Update fuel based on distance traveled"""
        fuel_consumption_rate = 0.1  # Example rate
        self.fuel -= distance_traveled * fuel_consumption_rate

    def load_cargo(self, cargo):
        """Load cargo into the truck"""
        self.cargo = cargo

    def deliver_cargo(self):
        """Deliver and remove cargo"""
        delivered_cargo = self.cargo
        self.cargo = None
        return delivered_cargo
