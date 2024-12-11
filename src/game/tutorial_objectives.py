from typing import Dict, List, Optional
import pygame

class TutorialObjective:
    def __init__(self, title: str, description: str, reward: float, completed: bool = False):
        self.title = title
        self.description = description
        self.reward = reward
        self.completed = completed
        self.completion_time = None

class TutorialManager:
    def __init__(self, screen, tts_engine, player_data: Dict):
        self.screen = screen
        self.tts_engine = tts_engine
        self.player_data = player_data
        self.font = pygame.font.Font(None, 32)
        self.small_font = pygame.font.Font(None, 24)
        
        # Tutorial message system
        self.current_messages = []
        self.message_index = 0
        
        # Colors
        self.WHITE = (255, 255, 255)
        self.BLACK = (0, 0, 0)
        self.GRAY = (128, 128, 128)
        self.GREEN = (0, 255, 0)
        self.YELLOW = (255, 255, 0)
        
        # Initialize tutorial objectives
        self.objectives = [
            TutorialObjective(
                "Find a Job Location",
                "Visit a truck stop, freight terminal, or distribution center to find work",
                250.0
            ),
            TutorialObjective(
                "Accept Your First Job",
                "Accept a delivery job that matches your CDL license",
                500.0
            ),
            TutorialObjective(
                "Complete First Delivery",
                "Successfully deliver your first cargo to its destination",
                1000.0
            ),
            TutorialObjective(
                "Visit Different Location Types",
                "Visit at least one truck stop, one freight terminal, and one distribution center",
                750.0
            ),
            TutorialObjective(
                "Maintain Cargo Safety",
                "Complete a delivery with no cargo damage",
                500.0
            )
        ]
        
        self.show_tutorial = True
        self.current_objective_index = 0
        
    def update_objective(self, objective_type: str) -> Optional[float]:
        """Update objective progress and return reward if completed."""
        print(f"\nTutorial: update_objective called with type: {objective_type}")
        if not self.show_tutorial:
            return None
            
        reward = None
        current_obj = self.objectives[self.current_objective_index]
        
        # Announce current objective when starting
        if objective_type == "start_tutorial":
            print("Tutorial: Initializing tutorial messages")
            self.current_messages = [
                "Welcome to Freight Fate. Press Enter to continue through tutorial messages.",
                "Use arrow keys to drive your truck. Up arrow for gas, down for brake.",
                "Press M to open your map and find nearby job locations.",
                "Look for truck stops, freight terminals, or distribution centers marked on your map.",
                "Drive to any of these locations to find work.",
                f"Your first objective: {current_obj.title}.",
                f"{current_obj.description}",
                "Press Tab at any time to hear your current objective again.",
                "Press F1 for help with controls and gameplay."
            ]
            # Speak welcome immediately
            self.tts_engine.output(self.current_messages[0])
            self.message_index = 1  # Set up for next message
        
        if objective_type == "visit_location" and current_obj.title == "Find a Job Location":
            current_obj.completed = True
            reward = current_obj.reward
            self.advance_tutorial()
            
        elif objective_type == "accept_job" and current_obj.title == "Accept Your First Job":
            current_obj.completed = True
            reward = current_obj.reward
            self.advance_tutorial()
            
        elif objective_type == "complete_delivery" and current_obj.title == "Complete First Delivery":
            current_obj.completed = True
            reward = current_obj.reward
            self.advance_tutorial()
            
        elif objective_type == "visit_all_types":
            visited_types = set(self.player_data.get('visited_location_types', []))
            if len(visited_types) >= 3 and current_obj.title == "Visit Different Location Types":
                current_obj.completed = True
                reward = current_obj.reward
                self.advance_tutorial()
            else:
                # Progress update
                remaining = 3 - len(visited_types)
                if remaining > 0:
                    self.tts_engine.output(f"Progress: Visit {remaining} more location types to complete this objective.")
                
        elif objective_type == "perfect_delivery" and current_obj.title == "Maintain Cargo Safety":
            current_obj.completed = True
            reward = current_obj.reward
            self.advance_tutorial()
        
        # Provide hints if no progress in a while
        elif objective_type == "check_progress":
            if current_obj.title == "Find a Job Location":
                self.tts_engine.output("Hint: Press M to open your map. Look for truck stops or freight terminals marked on the map. Drive to any of these locations using arrow keys.")
            elif current_obj.title == "Accept Your First Job":
                self.tts_engine.output("Hint: Press Enter at a job location to view available jobs.")
            elif current_obj.title == "Complete First Delivery":
                self.tts_engine.output("Hint: Follow your GPS and maintain safe driving practices.")
            
        if reward:
            self.speak_objective_completed(current_obj)
            
        return reward
        
    def advance_tutorial(self):
        """Advance to the next tutorial objective."""
        current_obj = self.objectives[self.current_objective_index]
        self.tts_engine.output(f"Objective completed: {current_obj.title}. Earned ${current_obj.reward:.2f}")
        
        self.current_objective_index += 1
        if self.current_objective_index >= len(self.objectives):
            self.show_tutorial = False
            self.speak_tutorial_completed()
        else:
            self.speak_new_objective()
            
    def render(self):
        """Render the current tutorial objective."""
        if not self.show_tutorial:
            return
            
        # Draw tutorial box
        box_rect = pygame.Rect(10, 10, 300, 150)
        pygame.draw.rect(self.screen, self.BLACK, box_rect)
        pygame.draw.rect(self.screen, self.WHITE, box_rect, 2)
        
        # Draw tutorial title
        title = self.font.render("Tutorial Objectives", True, self.YELLOW)
        self.screen.blit(title, (20, 20))
        
        # Draw current objective
        current_obj = self.objectives[self.current_objective_index]
        obj_title = self.small_font.render(current_obj.title, True, self.WHITE)
        obj_desc = self.small_font.render(current_obj.description, True, self.GRAY)
        reward_text = self.small_font.render(f"Reward: ${current_obj.reward:.2f}", True, self.GREEN)
        
        self.screen.blit(obj_title, (20, 60))
        self.screen.blit(obj_desc, (20, 90))
        self.screen.blit(reward_text, (20, 120))
        
    def speak_objective_completed(self, objective: TutorialObjective):
        """Announce completion of an objective."""
        text = f"Objective completed: {objective.title}. Earned ${objective.reward:.2f}"
        self.tts_engine.output(text)

    def speak_new_objective(self):
        """Announce the new current objective."""
        current_obj = self.objectives[self.current_objective_index]
        text = f"New objective: {current_obj.title}. {current_obj.description}"
        self.tts_engine.output(text)

    def speak_tutorial_completed(self):
        """Announce completion of the tutorial."""
        text = "Congratulations! You've completed all tutorial objectives. You're ready for the open road!"
        self.tts_engine.output(text)
        
    def skip_tutorial(self):
        """Skip the tutorial."""
        self.show_tutorial = False
        text = "Tutorial skipped. Good luck on the road!"
        self.tts_engine.output(text)

    def handle_event(self, event):
        """Handle pygame events."""
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_RETURN and self.current_messages:
                self.speak_next_message()
            elif event.key == pygame.K_TAB:
                self.speak_current_objective()

    def speak_next_message(self):
        """Speak the next tutorial message."""
        if self.message_index < len(self.current_messages):
            message = self.current_messages[self.message_index]
            print(f"Tutorial: Speaking message {self.message_index + 1}/{len(self.current_messages)}: {message}")
            self.tts_engine.output(message)
            self.message_index += 1
            
    def speak_current_objective(self):
        """Speak the current objective and its description."""
        if self.current_objective_index < len(self.objectives):
            obj = self.objectives[self.current_objective_index]
            self.tts_engine.output(f"Current objective: {obj.title}. {obj.description}")
