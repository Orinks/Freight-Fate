from typing import Dict, List, Optional
import pygame

class TutorialObjective:
    def __init__(self, title: str, description: str, reward: float, completed: bool = False, help_text: str = ""):
        self.title = title
        self.description = description
        self.reward = reward
        self.completed = completed
        self.completion_time = None
        self.help_text = help_text

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
                "Basic Controls",
                "Learn the basic truck controls",
                100.0,
                help_text="Use W/S for acceleration/brake, A/D for steering. Press H for help."
            ),
            TutorialObjective(
                "Start Your Engine",
                "Press 'E' to start your truck's engine",
                50.0,
                help_text="Look for the engine status indicator in your HUD"
            ),
            TutorialObjective(
                "Practice Driving",
                "Drive forward and come to a complete stop",
                200.0,
                help_text="Gently press W to move forward, then S to brake smoothly"
            ),
            TutorialObjective(
                "Navigate to Job Location",
                "Follow the GPS to reach a nearby job location",
                300.0,
                help_text="Watch for navigation arrows and distance indicators"
            ),
            TutorialObjective(
                "Find Available Jobs",
                "Check the job board for available deliveries",
                250.0,
                help_text="Look for jobs matching your current location and license"
            ),
            TutorialObjective(
                "Accept First Job",
                "Choose and accept a suitable delivery job",
                500.0,
                help_text="Consider distance, pay, and cargo type when selecting"
            ),
            TutorialObjective(
                "Load Cargo",
                "Position your truck at the loading dock",
                200.0,
                help_text="Align your trailer with the loading markers"
            ),
            TutorialObjective(
                "Safe Driving",
                "Drive 1 mile without accidents or violations",
                400.0,
                help_text="Watch your speed and maintain safe following distance"
            ),
            TutorialObjective(
                "Complete First Delivery",
                "Deliver your cargo safely to destination",
                1000.0,
                help_text="Follow route guidance and traffic rules"
            )
        ]
        
        self.show_tutorial = True
        self.current_objective_index = 0
        
    def update_objective(self, objective_type: str, **kwargs) -> Optional[float]:
        """Update objective progress and return reward if completed."""
        print(f"\nTutorial: update_objective called with type: {objective_type}")
        if not self.show_tutorial:
            return None
            
        reward = None
        current_obj = self.objectives[self.current_objective_index]
        
        # Handle start tutorial
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
            return None

        # Handle objective completions
        if objective_type == "controls_learned" and current_obj.title == "Basic Controls":
            current_obj.completed = True
            reward = current_obj.reward
            self.advance_tutorial()
            
        elif objective_type == "engine_started" and current_obj.title == "Start Your Engine":
            current_obj.completed = True
            reward = current_obj.reward
            self.advance_tutorial()
            
        elif objective_type == "practice_complete" and current_obj.title == "Practice Driving":
            current_obj.completed = True
            reward = current_obj.reward
            self.advance_tutorial()
            
        elif objective_type == "reached_location" and current_obj.title == "Navigate to Job Location":
            current_obj.completed = True
            reward = current_obj.reward
            self.advance_tutorial()
            
        elif objective_type == "viewed_jobs" and current_obj.title == "Find Available Jobs":
            current_obj.completed = True
            reward = current_obj.reward
            self.advance_tutorial()
            
        elif objective_type == "job_accepted" and current_obj.title == "Accept First Job":
            current_obj.completed = True
            reward = current_obj.reward
            self.advance_tutorial()
            
        elif objective_type == "cargo_loaded" and current_obj.title == "Load Cargo":
            current_obj.completed = True
            reward = current_obj.reward
            self.advance_tutorial()
            
        elif objective_type == "safe_mile" and current_obj.title == "Safe Driving":
            current_obj.completed = True
            reward = current_obj.reward
            self.advance_tutorial()
            
        elif objective_type == "delivery_complete" and current_obj.title == "Complete First Delivery":
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
            
        # Draw tutorial box with increased size for help text
        box_rect = pygame.Rect(10, 10, 300, 200)
        
        # Draw semi-transparent background
        s = pygame.Surface((300, 200))
        s.set_alpha(200)
        s.fill(self.BLACK)
        self.screen.blit(s, (10, 10))
        
        # Draw border
        pygame.draw.rect(self.screen, self.WHITE, box_rect, 2)
        
        # Draw tutorial title
        title = self.font.render("Tutorial", True, self.YELLOW)
        self.screen.blit(title, (20, 20))
        
        # Draw current objective
        current_obj = self.objectives[self.current_objective_index]
        obj_title = self.small_font.render(current_obj.title, True, self.WHITE)
        
        # Split description into multiple lines if needed
        words = current_obj.description.split()
        lines = []
        current_line = []
        for word in words:
            current_line.append(word)
            test_line = ' '.join(current_line)
            if self.small_font.size(test_line)[0] > 280:
                current_line.pop()
                lines.append(' '.join(current_line))
                current_line = [word]
        if current_line:
            lines.append(' '.join(current_line))
        
        # Draw objective info
        self.screen.blit(obj_title, (20, 50))
        for i, line in enumerate(lines):
            desc_line = self.small_font.render(line, True, self.GRAY)
            self.screen.blit(desc_line, (20, 80 + i * 25))
        
        # Draw help hint
        help_hint = self.small_font.render("Press H for help", True, self.GREEN)
        self.screen.blit(help_hint, (20, 170))
        
        # Draw reward
        reward_text = self.small_font.render(f"Reward: ${current_obj.reward:.2f}", True, self.GREEN)
        self.screen.blit(reward_text, (150, 170))
        
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
