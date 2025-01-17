"""Settings menu for the game."""
import pygame
from .menu import Menu, MenuItem, MenuSection

class SettingsMenu(Menu):
    def __init__(self, screen, tts_engine, settings, sound_manager, on_tts_change=None):
        """Initialize the settings menu.
        
        Args:
            screen: Pygame display surface
            tts_engine: Text-to-speech engine
            settings: Settings instance
            sound_manager: Sound manager instance
            on_tts_change: Callback for when TTS engine is reinitialized
        """
        super().__init__(screen, tts_engine)
        self.settings = settings
        self.sound_manager = sound_manager
        self.on_tts_change = on_tts_change
        
        # Menu items
        self.menu_items = [
            MenuSection('Audio Settings', [
                MenuItem('Volume', 'toggle_volume'),
                MenuItem('Music Volume', 'toggle_music_volume'),
                MenuItem('Speech Volume', 'toggle_speech_volume'),
                MenuItem('Speech Engine', 'toggle_speech_engine'),
                MenuItem('SAPI Voice', 'select_sapi_voice', visible_when=lambda: self.settings.speech_engine_mode == "sapi"),
                MenuItem('Speech Rate', 'adjust_speech_rate', visible_when=lambda: self.settings.speech_engine_mode == "sapi"),
                MenuItem('Speech Pitch', 'adjust_speech_pitch', visible_when=lambda: self.settings.speech_engine_mode == "sapi"),
            ]),
            MenuSection('Gameplay Settings', [
                MenuItem('Automatic Transmission', 'toggle_transmission')
            ]),
            MenuItem('Unit System', 'toggle_units'),
            MenuItem('Back', 'back')
        ]
        self.selected_index = 0
        self.title = 'Settings'
        
        # Initial announcement
        if self.tts_engine:
            self.tts_engine.output("Settings Menu. Use arrow keys to navigate options, Enter to adjust settings, Tab for help.")

    def toggle_units(self):
        """Toggle between imperial and metric units."""
        if self.sound_manager:
            self.sound_manager.play_sound('menu_select')
        self.settings.toggle_units()
        self.settings.save_settings()
        # Announce the change
        current_system = 'Imperial' if self.settings.use_imperial else 'Metric'
        if self.tts_engine:
            self.tts_engine.output(f"Unit system changed to {current_system}. This affects distances and weights in the game.")
        return None  # Stay in menu

    def toggle_speech_engine(self):
        """Toggle speech engine mode."""
        if self.sound_manager:
            self.sound_manager.play_sound('menu_select')
        self.settings.toggle_speech_engine_mode()
        self.settings.save_settings()
        
        # Update engine mode instead of recreating it
        if self.tts_engine:
            self.tts_engine.set_mode(self.settings.speech_engine_mode)
            
            # Notify game states about the engine update
            if self.on_tts_change:
                self.on_tts_change(self.tts_engine)
            
            # Announce the change
            current_mode = 'SAPI' if self.settings.speech_engine_mode == 'sapi' else 'Default'
            if current_mode == 'SAPI':
                self.tts_engine.output(f"Speech engine changed to {current_mode}. Additional voice settings are now available.")
            else:
                self.tts_engine.output(f"Speech engine changed to {current_mode}.")

    def select_sapi_voice(self):
        """Select a SAPI voice from available voices."""
        if not hasattr(self.tts_engine, 'get_available_voices'):
            self.tts_engine.output("SAPI voice selection not available")
            return
            
        voices = self.tts_engine.get_available_voices()
        if not voices:
            self.tts_engine.output("No SAPI voices available")
            return
            
        # Play selection sound
        if self.sound_manager:
            self.sound_manager.play_sound('menu_select')
            
        # Find current voice index
        current_voice = self.settings.sapi_voice
        try:
            current_index = voices.index(current_voice) if current_voice in voices else 0
        except ValueError:
            current_index = 0
            
        # Cycle to next voice
        next_index = (current_index + 1) % len(voices)
        next_voice = voices[next_index]
        
        if self.tts_engine.set_voice_by_name(next_voice):
            self.settings.sapi_voice = next_voice
            self.tts_engine.output(f"Voice set to {next_voice}")
        else:
            self.tts_engine.output("Failed to set voice")

    def adjust_speech_rate(self):
        """Adjust SAPI speech rate."""
        if not hasattr(self.tts_engine, 'set_rate'):
            self.tts_engine.output("Speech rate adjustment not available")
            return
            
        # Play selection sound
        if self.sound_manager:
            self.sound_manager.play_sound('menu_select')
            
        # Cycle through predefined rates: 25 (slow), 50 (normal), 75 (fast)
        rates = [25, 50, 75]
        current_rate = self.settings.speech_rate
        
        # Find next rate
        try:
            current_index = rates.index(current_rate)
            next_index = (current_index + 1) % len(rates)
        except ValueError:
            next_index = 1  # Default to normal speed
            
        next_rate = rates[next_index]
        
        if self.tts_engine.set_rate(next_rate):
            self.settings.speech_rate = next_rate
            speed_name = "slow" if next_rate == 25 else "normal" if next_rate == 50 else "fast"
            self.tts_engine.output(f"Speech rate set to {speed_name}")
        else:
            self.tts_engine.output("Failed to set speech rate")

    def adjust_speech_pitch(self):
        """Adjust SAPI speech pitch."""
        if not hasattr(self.tts_engine, 'set_pitch'):
            self.tts_engine.output("Speech pitch adjustment not available")
            return
            
        # Play selection sound
        if self.sound_manager:
            self.sound_manager.play_sound('menu_select')
            
        # Cycle through predefined pitch levels: 25 (low), 50 (normal), 75 (high)
        pitches = [25, 50, 75]
        current_pitch = self.settings.speech_pitch
        
        # Find next pitch
        try:
            current_index = pitches.index(current_pitch)
            next_index = (current_index + 1) % len(pitches)
        except ValueError:
            next_index = 1  # Default to normal pitch
            
        next_pitch = pitches[next_index]
        
        if self.tts_engine.set_pitch(next_pitch):
            self.settings.speech_pitch = next_pitch
            pitch_name = "low" if next_pitch == 25 else "normal" if next_pitch == 50 else "high"
            self.tts_engine.output(f"Speech pitch set to {pitch_name}")
        else:
            self.tts_engine.output("Failed to set speech pitch")

    def get_visible_items(self):
        """Get a flat list of all visible menu items."""
        visible_items = []
        for item in self.menu_items:
            if isinstance(item, MenuSection):
                visible_items.extend([i for i in item.items if i.visible_when()])
            else:
                if item.visible_when():
                    visible_items.append(item)
        return visible_items

    def handle_input(self, event):
        """Handle input events."""
        if event.type == pygame.KEYDOWN:
            if event.key in [pygame.K_UP, pygame.K_DOWN]:
                # Play navigation sound
                if self.sound_manager:
                    self.sound_manager.play_sound('menu_nav')
                    
                # Update selection
                direction = -1 if event.key == pygame.K_UP else 1
                visible_items = self.get_visible_items()
                if visible_items:
                    self.selected_index = (self.selected_index + direction) % len(visible_items)
                    if self.tts_engine:
                        current_item = visible_items[self.selected_index]
                        # Add more context for settings items
                        if current_item.text == "Volume":
                            self.tts_engine.output("Volume - Adjust sound effects volume")
                        elif current_item.text == "Music Volume":
                            self.tts_engine.output("Music Volume - Adjust background music volume")
                        elif current_item.text == "Speech Volume":
                            self.tts_engine.output("Speech Volume - Adjust voice announcements volume")
                        elif current_item.text == "Speech Engine":
                            current_mode = 'SAPI' if self.settings.speech_engine_mode == 'sapi' else 'Default'
                            self.tts_engine.output(f"Speech Engine - Currently set to {current_mode}")
                        elif current_item.text == "SAPI Voice":
                            self.tts_engine.output(f"SAPI Voice - Select different voice for announcements")
                        elif current_item.text == "Speech Rate":
                            speed_name = "slow" if self.settings.speech_rate == 25 else "normal" if self.settings.speech_rate == 50 else "fast"
                            self.tts_engine.output(f"Speech Rate - Currently set to {speed_name}")
                        elif current_item.text == "Speech Pitch":
                            pitch_name = "low" if self.settings.speech_pitch == 25 else "normal" if self.settings.speech_pitch == 50 else "high"
                            self.tts_engine.output(f"Speech Pitch - Currently set to {pitch_name}")
                        elif current_item.text == "Unit System":
                            current_system = 'Imperial' if self.settings.use_imperial else 'Metric'
                            self.tts_engine.output(f"Unit System - Currently set to {current_system}")
                        elif current_item.text == "Back":
                            self.tts_engine.output("Back - Return to main menu")
                        else:
                            self.tts_engine.output(current_item.text)
            
            elif event.key == pygame.K_TAB:
                # Announce help information
                if self.tts_engine:
                    help_text = (
                        "Settings Controls: "
                        "Use Up and Down arrows to navigate through options, "
                        "Enter to adjust a setting, "
                        "Tab for this help message, "
                        "and Escape to return to the main menu. "
                        "Press F1 for detailed information about each setting."
                    )
                    self.tts_engine.output(help_text)
                    
            elif event.key == pygame.K_F1:
                # Announce detailed settings help
                if self.tts_engine:
                    help_text = (
                        "Settings Help: "
                        "Volume controls adjust different sound levels. "
                        "Speech Engine toggles between Default and SAPI modes. "
                        "When SAPI is enabled, you can adjust voice, rate, and pitch. "
                        "Unit System switches between Imperial and Metric measurements. "
                        "All settings are saved automatically."
                    )
                    self.tts_engine.output(help_text)
                    
            elif event.key == pygame.K_RETURN:
                # Play selection sound
                if self.sound_manager:
                    self.sound_manager.play_sound('menu_select')
                    
                # Handle selection
                visible_items = self.get_visible_items()
                if not visible_items:
                    return None
                    
                selected_item = visible_items[self.selected_index]
                
                if selected_item.action == 'back':
                    if self.sound_manager:
                        self.sound_manager.play_sound('menu_back')
                    return 'back'
                elif selected_item.action == 'toggle_units':
                    return self.toggle_units()
                elif selected_item.action == 'toggle_speech_engine':
                    return self.toggle_speech_engine()
                elif selected_item.action == 'select_sapi_voice':
                    return self.select_sapi_voice()
                elif selected_item.action == 'adjust_speech_rate':
                    return self.adjust_speech_rate()
                elif selected_item.action == 'adjust_speech_pitch':
                    return self.adjust_speech_pitch()
                elif selected_item.action == 'toggle_transmission':
                    return self.toggle_transmission()
                    
            elif event.key == pygame.K_ESCAPE:
                # Play back sound
                if self.sound_manager:
                    self.sound_manager.play_sound('menu_back')
                return 'back'
                
        return None

    def render(self):
        """Render the settings menu."""
        self.screen.fill((0, 0, 0))  # Black background
        
        # Draw title
        title_surface = self.font.render(self.title, True, self.WHITE)
        title_rect = title_surface.get_rect(center=(self.screen.get_width() // 2, 100))
        self.screen.blit(title_surface, title_rect)
        
        # Get all visible items for selection highlighting
        visible_items = self.get_visible_items()
        visible_index = 0
        
        # Draw menu items
        y_position = 200
        for item in self.menu_items:
            if isinstance(item, MenuSection):
                # Draw section title
                section_title = self.font.render(item.title, True, self.WHITE)
                section_rect = section_title.get_rect(center=(self.screen.get_width() // 2, y_position))
                self.screen.blit(section_title, section_rect)
                y_position += 40
                
                # Draw section items
                for sub_item in item.items:
                    if sub_item.visible_when():
                        if sub_item.text == 'Speech Engine':
                            text = f"Speech Engine: {'SAPI' if self.settings.speech_engine_mode == 'sapi' else 'Default'}"
                        elif sub_item.text == 'Automatic Transmission':
                            text = f"Transmission: {'Automatic' if self.settings.auto_transmission else 'Manual'}"
                        else:
                            text = sub_item.text
                            
                        color = self.YELLOW if visible_index == self.selected_index else self.WHITE
                        text_surface = self.font.render(text, True, color)
                        text_rect = text_surface.get_rect(center=(self.screen.get_width() // 2, y_position))
                        self.screen.blit(text_surface, text_rect)
                        y_position += 40
                        visible_index += 1
            else:
                if item.visible_when():
                    if item.text == 'Unit System':
                        text = f"Unit System: {'Imperial' if self.settings.use_imperial else 'Metric'}"
                    else:
                        text = item.text
                        
                    color = self.YELLOW if visible_index == self.selected_index else self.WHITE
                    text_surface = self.font.render(text, True, color)
                    text_rect = text_surface.get_rect(center=(self.screen.get_width() // 2, y_position))
                    self.screen.blit(text_surface, text_rect)
                    y_position += 40
                    visible_index += 1
        
        pygame.display.flip()

    def announce_current_item(self):
        """Announce the current menu item via TTS."""
        if not self.tts_engine:
            return
            
        # Get list of visible items
        visible_items = self.get_visible_items()
        visible_index = 0
        
        for item in self.menu_items:
            if isinstance(item, MenuSection):
                for sub_item in item.items:
                    if sub_item.visible_when():
                        if visible_index == self.selected_index:
                            if sub_item.text == 'Unit System':
                                current_system = 'Imperial' if self.settings.use_imperial else 'Metric'
                                self.tts_engine.output(f"Unit System: Currently set to {current_system}")
                            elif sub_item.text == 'Speech Engine':
                                current_mode = 'SAPI' if self.settings.speech_engine_mode == 'sapi' else 'Default'
                                self.tts_engine.output(f"Speech Engine: Currently set to {current_mode}")
                            else:
                                self.tts_engine.output(sub_item.text)
                        visible_index += 1
            else:
                if item.visible_when():
                    if visible_index == self.selected_index:
                        if item.text == 'Unit System':
                            current_system = 'Imperial' if self.settings.use_imperial else 'Metric'
                            self.tts_engine.output(f"Unit System: Currently set to {current_system}")
                        elif item.text == 'Speech Engine':
                            current_mode = 'SAPI' if self.settings.speech_engine_mode == 'sapi' else 'Default'
                            self.tts_engine.output(f"Speech Engine: Currently set to {current_mode}")
                        else:
                            self.tts_engine.output(item.text)
                    visible_index += 1

    def toggle_transmission(self):
        """Toggle automatic transmission setting."""
        if self.sound_manager:
            self.sound_manager.play_sound('menu_select')
        self.settings.toggle_transmission()
        self.settings.save_settings()
        current_mode = 'Automatic' if self.settings.auto_transmission else 'Manual'
        if self.tts_engine:
            self.tts_engine.output(f"Transmission set to {current_mode}")
        return None

    # Colors
    WHITE = (255, 255, 255)
    YELLOW = (255, 255, 0)
