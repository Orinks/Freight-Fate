import pygame
import random
import json
from datetime import datetime
from typing import List, Optional, Dict
from .jobs import Job, JobGenerator
from .ui_elements import Button, TextBox, ScrollableList

class JobBoard:
    def __init__(self, screen, tts_engine, cities_data, font_size=32):
        self.screen = screen
        self.tts_engine = tts_engine
        self.font = pygame.font.Font(None, font_size)
        self.job_generator = JobGenerator(cities_data)
        self.available_jobs: List[Job] = []
        self.current_job: Optional[Job] = None
        self.selected_index = 0
        
        # Colors
        self.WHITE = (255, 255, 255)
        self.BLACK = (0, 0, 0)
        self.GRAY = (128, 128, 128)
        self.YELLOW = (255, 255, 0)
        self.GREEN = (0, 255, 0)
        self.RED = (255, 0, 0)
        
        # Create UI elements
        self.refresh_button = Button(
            self.screen,
            "Refresh Jobs",
            (self.screen.get_width() - 150, 50),
            (120, 40),
            self.WHITE,
            self.BLACK
        )
        
        self.accept_button = Button(
            self.screen,
            "Accept Job",
            (self.screen.get_width() - 150, self.screen.get_height() - 100),
            (120, 40),
            self.GREEN,
            self.BLACK
        )
        
        self.job_list = ScrollableList(
            self.screen,
            (50, 100),
            (self.screen.get_width() - 250, self.screen.get_height() - 200),
            self.WHITE,
            self.BLACK
        )
        
        self.details_box = TextBox(
            self.screen,
            (self.screen.get_width() - 200, 150),
            (180, 300),
            self.WHITE,
            self.BLACK
        )

    def refresh_jobs(self, current_city: str, player_level: int, current_location: Dict = None):
        """Refresh the list of available jobs based on current city and location."""
        self.available_jobs.clear()
        
        if not current_location:
            self.tts_engine.output("You must be at a job location to view available jobs.")
            return
            
        # Get location type and available job types
        location_type = current_location['type']
        location_name = current_location['name'].split(' - ')[0]  # Remove location suffix
        
        if location_type == 'Truck Stop':
            job_info = self.job_generator.cities_data['job_locations']['truck_stops'][location_name]
        elif location_type == 'Freight Terminal':
            job_info = self.job_generator.cities_data['job_locations']['freight_terminals'][location_name]
        else:  # Distribution Center
            job_info = self.job_generator.cities_data['job_locations']['distribution_centers'][location_name]
            
        available_job_types = job_info.get('job_types', [])
        
        # Generate jobs based on location type and available job types
        num_jobs = random.randint(3, 7)
        for _ in range(num_jobs):
            job_type = random.choice(available_job_types)
            job = self.job_generator.generate_job(current_city, job_type, player_level)
            self.available_jobs.append(job)
            
        self.selected_index = 0 if self.available_jobs else -1
        self.speak_job_count()

    def format_job_list_item(self, job: Job, selected: bool = False) -> str:
        """Format a job for display in the list."""
        time_remaining = job.time_remaining()
        hours = int(time_remaining.total_seconds() / 3600)
        minutes = int((time_remaining.total_seconds() % 3600) / 60)
        
        return (
            f"{'→ ' if selected else '  '}"
            f"{job.cargo.name} to {job.end_city} "
            f"(${job.base_pay:,.2f} + ${job.bonus_pay:,.2f} bonus) "
            f"[{hours}h {minutes}m remaining]"
        )

    def format_job_details(self, job: Job) -> str:
        """Format detailed job information."""
        return (
            f"Cargo: {job.cargo.name}\n"
            f"Weight: {job.cargo.weight:.1f} tons\n"
            f"Value: ${job.cargo.value:,.2f}\n"
            f"From: {job.start_city}\n"
            f"To: {job.end_city}\n"
            f"Base Pay: ${job.base_pay:,.2f}\n"
            f"Bonus Pay: ${job.bonus_pay:,.2f}\n"
            f"Time Left: {int(job.time_remaining().total_seconds() / 3600)}h "
            f"{int((job.time_remaining().total_seconds() % 3600) / 60)}m\n"
            f"License: {job.required_license}\n"
            f"{'FRAGILE' if job.cargo.fragile else ''}\n"
            f"{'HAZARDOUS' if job.cargo.hazardous else ''}"
        )

    def render(self):
        """Render the job board interface."""
        # Draw background
        self.screen.fill(self.BLACK)
        
        # Draw title
        title = self.font.render("Job Board", True, self.WHITE)
        title_rect = title.get_rect(center=(self.screen.get_width() // 2, 50))
        self.screen.blit(title, title_rect)
        
        # Draw job list
        job_items = [
            self.format_job_list_item(job, i == self.selected_index)
            for i, job in enumerate(self.available_jobs)
        ]
        self.job_list.update(job_items)
        
        # Draw job details if a job is selected
        if self.available_jobs and 0 <= self.selected_index < len(self.available_jobs):
            details = self.format_job_details(self.available_jobs[self.selected_index])
            self.details_box.update(details)
        
        # Draw buttons
        self.refresh_button.draw()
        self.accept_button.draw()
        
        # Draw instructions
        instructions = [
            "↑/↓: Select Job",
            "ENTER: Accept Job",
            "R: Refresh Jobs",
            "ESC: Back"
        ]
        y_pos = self.screen.get_height() - 150
        for instruction in instructions:
            text = self.font.render(instruction, True, self.GRAY)
            text_rect = text.get_rect(center=(self.screen.get_width() - 110, y_pos))
            self.screen.blit(text, text_rect)
            y_pos += 30
        
        pygame.display.flip()

    def handle_event(self, event, current_city: str, current_location: Dict = None) -> Optional[str]:
        """Handle user input events."""
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_UP:
                self.select_previous()
            elif event.key == pygame.K_DOWN:
                self.select_next()
            elif event.key == pygame.K_RETURN:
                return self.accept_job()
            elif event.key == pygame.K_r:
                self.refresh_jobs(current_city, 1, current_location)
            elif event.key == pygame.K_ESCAPE:
                return "back"
        
        # Handle mouse events for buttons
        elif event.type == pygame.MOUSEBUTTONDOWN:
            mouse_pos = pygame.mouse.get_pos()
            if self.refresh_button.is_clicked(mouse_pos):
                self.refresh_jobs(current_city, 1, current_location)
            elif self.accept_button.is_clicked(mouse_pos):
                return self.accept_job()
        
        return None

    def select_previous(self):
        """Select the previous job in the list."""
        if self.available_jobs:
            self.selected_index = (self.selected_index - 1) % len(self.available_jobs)
            self.speak_selected_job()

    def select_next(self):
        """Select the next job in the list."""
        if self.available_jobs:
            self.selected_index = (self.selected_index + 1) % len(self.available_jobs)
            self.speak_selected_job()

    def accept_job(self) -> Optional[str]:
        """Accept the currently selected job."""
        if self.available_jobs and 0 <= self.selected_index < len(self.available_jobs):
            self.current_job = self.available_jobs[self.selected_index]
            self.speak_job_accepted()
            return "accept_job"
        return None

    def speak_selected_job(self):
        """Speak the currently selected job details."""
        if self.available_jobs and 0 <= self.selected_index < len(self.available_jobs):
            job = self.available_jobs[self.selected_index]
            text = f"Selected job: {job.cargo.name} to {job.end_city} for ${job.base_pay:,.2f}"
            self.tts_engine.output(text)

    def speak_job_accepted(self):
        """Speak confirmation of job acceptance."""
        if self.current_job:
            text = f"Job accepted. Delivering {self.current_job.cargo.name} to {self.current_job.end_city}"
            self.tts_engine.output(text)

    def speak_job_count(self):
        """Speak the number of available jobs."""
        text = f"{len(self.available_jobs)} available jobs"
        self.tts_engine.output(text)
