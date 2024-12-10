"""Settings menu for the game."""
import pygame
from .menu import Menu, MenuItem

class SettingsMenu(Menu):
    def __init__(self, screen, tts_engine, settings):
        """Initialize the settings menu.
        
        Args:
            screen: Pygame display surface
            tts_engine: Text-to-speech engine
            settings: Settings instance
        """
        super().__init__(screen, tts_engine)
        self.settings = settings
        
        # Menu items
        self.states = {
            'main': {
                'items': [
                    MenuItem('Unit System', 'toggle_units'),
                    MenuItem('Back', 'back')
                ],
                'selected_index': 0,
                'title': 'Settings'
            }
        }
        self.current_state = 'main'
        
        # Colors
        self.WHITE = (255, 255, 255)
        self.YELLOW = (255, 255, 0)
        
    def toggle_units(self):
        """Toggle between imperial and metric units."""
        self.settings.toggle_units()
        self.settings.save_settings()
        # Announce the change
        current_system = 'Imperial' if self.settings.use_imperial else 'Metric'
        if self.tts_engine:
            self.tts_engine.output(f"Changed to {current_system} units")
        return None  # Stay in menu
        
    def render(self):
        """Render the settings menu."""
        self.screen.fill((0, 0, 0))  # Black background
        
        state = self.states[self.current_state]
        
        # Draw title
        title_surface = self.font.render(state['title'], True, self.WHITE)
        title_rect = title_surface.get_rect(center=(self.screen.get_width() // 2, 100))
        self.screen.blit(title_surface, title_rect)
        
        # Draw menu items
        start_y = 200
        for i, item in enumerate(state['items']):
            # Special handling for unit system menu item
            if item.text == 'Unit System':
                text = f"Unit System: {'Imperial' if self.settings.use_imperial else 'Metric'}"
            else:
                text = item.text
                
            color = self.YELLOW if i == state['selected_index'] else self.WHITE
            text_surface = self.font.render(text, True, color)
            text_rect = text_surface.get_rect(center=(self.screen.get_width() // 2, start_y + i * 50))
            self.screen.blit(text_surface, text_rect)
        
        pygame.display.flip()
        
    def handle_input(self, event):
        """Handle input events."""
        if event.type == pygame.KEYDOWN:
            state = self.states[self.current_state]
            
            if event.key == pygame.K_UP:
                state['selected_index'] = (state['selected_index'] - 1) % len(state['items'])
                self.announce_current_item()
            elif event.key == pygame.K_DOWN:
                state['selected_index'] = (state['selected_index'] + 1) % len(state['items'])
                self.announce_current_item()
            elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
                selected_item = state['items'][state['selected_index']]
                if selected_item.action == 'toggle_units':
                    self.toggle_units()
                    self.announce_current_item()
                elif selected_item.action == 'back':
                    return 'back'
            elif event.key == pygame.K_ESCAPE:
                return 'back'
        return None
        
    def announce_current_item(self):
        """Announce the current menu item via TTS."""
        if not self.tts_engine:
            return
            
        state = self.states[self.current_state]
        item = state['items'][state['selected_index']]
        if item.text == 'Unit System':
            current_system = 'Imperial' if self.settings.use_imperial else 'Metric'
            self.tts_engine.output(f"Unit System: Currently set to {current_system}")
        else:
            self.tts_engine.output(item.text)
