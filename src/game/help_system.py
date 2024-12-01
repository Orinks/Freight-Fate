import pygame
from typing import Dict, List, Optional
from .ui_elements import Button, TextBox, ScrollableList

class HelpTopic:
    def __init__(self, title: str, content: str, subtopics: Optional[List['HelpTopic']] = None):
        self.title = title
        self.content = content
        self.subtopics = subtopics or []

class HelpSystem:
    def __init__(self, screen, tts_engine):
        self.screen = screen
        self.tts_engine = tts_engine
        self.font = pygame.font.Font(None, 32)
        self.small_font = pygame.font.Font(None, 24)
        
        # Colors
        self.WHITE = (255, 255, 255)
        self.BLACK = (0, 0, 0)
        self.GRAY = (128, 128, 128)
        self.BLUE = (100, 149, 237)
        self.YELLOW = (255, 255, 0)
        
        # Help topics
        self.topics = [
            HelpTopic("Getting Started", 
                """Welcome to Freight Fate! Here's how to begin your trucking career:
                
                1. Start in your initial city (New York)
                2. Find a job location (truck stop, terminal, or distribution center)
                3. Accept a job that matches your license
                4. Plan your route and make the delivery
                
                Press F1 at any time to open this help menu."""),
                
            HelpTopic("Job Locations", 
                """There are three types of job locations:
                
                • Truck Stops: General freight, refrigerated, hazmat
                • Freight Terminals: LTL freight, full truckload
                • Distribution Centers: Retail freight, express
                
                Each location offers different types of jobs and services.
                Visit the location to view available jobs."""),
                
            HelpTopic("Licenses & Qualifications", 
                """Different jobs require different licenses:
                
                • Class A CDL: All trailer types
                • Hazmat Endorsement: Dangerous goods
                • Tanker Endorsement: Liquid cargo
                • Double/Triple: Multiple trailers
                
                Upgrade your licenses to access better-paying jobs."""),
                
            HelpTopic("Navigation & Driving", 
                """Control your truck with:
                
                • Arrow keys: Steering
                • Space: Brake
                • Shift: Change gears
                • Tab: Quick access to job board
                
                Watch for:
                • Speed limits
                • Weather conditions
                • Traffic signals
                • Road hazards"""),
                
            HelpTopic("Cargo Care", 
                """Protect your cargo during transport:
                
                • Monitor cargo temperature
                • Avoid sudden braking
                • Take breaks when tired
                • Secure load properly
                
                Damaged cargo reduces pay and reputation."""),
                
            HelpTopic("Money & Experience", 
                """Earn money and experience through:
                
                • Completed deliveries
                • Bonus objectives
                • Safe driving
                • Time management
                
                Use earnings to:
                • Upgrade licenses
                • Repair truck
                • Buy fuel
                • Purchase upgrades"""),
                
            HelpTopic("Weather & Conditions", 
                """Different conditions affect driving:
                
                • Rain: Reduced traction
                • Snow: Slower speeds
                • Fog: Limited visibility
                • Wind: Trailer stability
                
                Check weather before trips."""),
                
            HelpTopic("Keyboard Controls", 
                """Essential controls:
                
                • F1: Help menu
                • ESC: Pause/Menu
                • Tab: Job board
                • M: Map view
                • C: Cargo status
                • T: Truck status
                • R: Repair menu""")
        ]
        
        # UI Elements
        self.topic_list = ScrollableList(
            self.screen,
            (50, 100),
            (300, self.screen.get_height() - 200),
            self.WHITE,
            self.BLACK
        )
        
        self.content_box = TextBox(
            self.screen,
            (400, 100),
            (self.screen.get_width() - 450, self.screen.get_height() - 200),
            self.WHITE,
            self.BLACK
        )
        
        self.back_button = Button(
            self.screen,
            "Back (ESC)",
            (50, self.screen.get_height() - 80),
            (100, 40),
            self.BLUE,
            self.WHITE
        )
        
        self.speak_button = Button(
            self.screen,
            "Read Aloud (Space)",
            (170, self.screen.get_height() - 80),
            (150, 40),
            self.BLUE,
            self.WHITE
        )
        
        # State
        self.selected_topic_index = 0
        self.visible = False
        
    def toggle_visibility(self):
        """Toggle help system visibility."""
        self.visible = not self.visible
        if self.visible:
            self.speak_welcome()
        
    def render(self):
        """Render the help system if visible."""
        if not self.visible:
            return
            
        # Draw semi-transparent background
        overlay = pygame.Surface((self.screen.get_width(), self.screen.get_height()))
        overlay.fill(self.BLACK)
        overlay.set_alpha(200)
        self.screen.blit(overlay, (0, 0))
        
        # Draw title
        title = self.font.render("Help & Documentation", True, self.YELLOW)
        title_rect = title.get_rect(center=(self.screen.get_width() // 2, 50))
        self.screen.blit(title, title_rect)
        
        # Draw topic list
        topic_items = [
            f"{'→ ' if i == self.selected_topic_index else '  '}{topic.title}"
            for i, topic in enumerate(self.topics)
        ]
        self.topic_list.update(topic_items)
        self.topic_list.draw()
        
        # Draw content
        if 0 <= self.selected_topic_index < len(self.topics):
            current_topic = self.topics[self.selected_topic_index]
            self.content_box.update(current_topic.content)
            self.content_box.draw()
        
        # Draw buttons
        self.back_button.draw()
        self.speak_button.draw()
        
    def handle_event(self, event) -> Optional[str]:
        """Handle user input events."""
        if not self.visible:
            if event.type == pygame.KEYDOWN and event.key == pygame.K_F1:
                self.toggle_visibility()
            return None
            
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                self.toggle_visibility()
                return "back"
            elif event.key == pygame.K_UP:
                self.select_previous()
            elif event.key == pygame.K_DOWN:
                self.select_next()
            elif event.key == pygame.K_SPACE:
                self.speak_current_topic()
                
        elif event.type == pygame.MOUSEBUTTONDOWN:
            mouse_pos = pygame.mouse.get_pos()
            if self.back_button.is_clicked(mouse_pos):
                self.toggle_visibility()
                return "back"
            elif self.speak_button.is_clicked(mouse_pos):
                self.speak_current_topic()
                
        return None
        
    def select_previous(self):
        """Select the previous topic."""
        if self.topics:
            self.selected_topic_index = (self.selected_topic_index - 1) % len(self.topics)
            self.speak_topic_title()
            
    def select_next(self):
        """Select the next topic."""
        if self.topics:
            self.selected_topic_index = (self.selected_topic_index + 1) % len(self.topics)
            self.speak_topic_title()
            
    def speak_welcome(self):
        """Speak welcome message when help system is opened."""
        text = "Help system opened. Use arrow keys to navigate topics. Press Space to read content."
        self.tts_engine.output(text)
        
    def speak_topic_title(self):
        """Speak the current topic title."""
        if 0 <= self.selected_topic_index < len(self.topics):
            text = f"Selected topic: {self.topics[self.selected_topic_index].title}"
            self.tts_engine.output(text)
            
    def speak_current_topic(self):
        """Read the current topic content aloud."""
        if 0 <= self.selected_topic_index < len(self.topics):
            topic = self.topics[self.selected_topic_index]
            text = f"{topic.title}. {topic.content}"
            self.tts_engine.output(text)
