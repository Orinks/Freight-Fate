import pygame
from typing import List, Tuple

class Button:
    def __init__(self, screen, text: str, position: Tuple[int, int], 
                 size: Tuple[int, int], text_color, bg_color, font_size=32):
        self.screen = screen
        self.text = text
        self.position = position
        self.size = size
        self.text_color = text_color
        self.bg_color = bg_color
        self.font = pygame.font.Font(None, font_size)
        self.rect = pygame.Rect(position[0], position[1], size[0], size[1])
        
    def draw(self):
        """Draw the button on the screen."""
        pygame.draw.rect(self.screen, self.bg_color, self.rect)
        pygame.draw.rect(self.screen, self.text_color, self.rect, 2)
        
        text_surface = self.font.render(self.text, True, self.text_color)
        text_rect = text_surface.get_rect(center=self.rect.center)
        self.screen.blit(text_surface, text_rect)
        
    def is_clicked(self, mouse_pos: Tuple[int, int]) -> bool:
        """Check if the button was clicked."""
        return self.rect.collidepoint(mouse_pos)

class TextBox:
    def __init__(self, screen, position: Tuple[int, int], 
                 size: Tuple[int, int], text_color, bg_color, font_size=28):
        self.screen = screen
        self.position = position
        self.size = size
        self.text_color = text_color
        self.bg_color = bg_color
        self.font = pygame.font.Font(None, font_size)
        self.rect = pygame.Rect(position[0], position[1], size[0], size[1])
        self.text_lines: List[str] = []
        self.line_height = font_size + 4
        
    def update(self, text: str):
        """Update the text in the box."""
        words = text.split()
        self.text_lines = []
        current_line = []
        
        for word in words:
            test_line = ' '.join(current_line + [word])
            test_surface = self.font.render(test_line, True, self.text_color)
            
            if test_surface.get_width() <= self.size[0] - 20:
                current_line.append(word)
            else:
                if current_line:
                    self.text_lines.append(' '.join(current_line))
                current_line = [word]
        
        if current_line:
            self.text_lines.append(' '.join(current_line))
        
        # Handle newlines in original text
        final_lines = []
        for line in self.text_lines:
            final_lines.extend(line.split('\n'))
        self.text_lines = final_lines
        
    def draw(self):
        """Draw the text box on the screen."""
        pygame.draw.rect(self.screen, self.bg_color, self.rect)
        pygame.draw.rect(self.screen, self.text_color, self.rect, 2)
        
        for i, line in enumerate(self.text_lines):
            if i * self.line_height < self.size[1] - self.line_height:
                text_surface = self.font.render(line, True, self.text_color)
                self.screen.blit(text_surface, 
                               (self.position[0] + 10, 
                                self.position[1] + 10 + i * self.line_height))

class ScrollableList:
    def __init__(self, screen, position: Tuple[int, int], 
                 size: Tuple[int, int], text_color, bg_color, font_size=28):
        self.screen = screen
        self.position = position
        self.size = size
        self.text_color = text_color
        self.bg_color = bg_color
        self.font = pygame.font.Font(None, font_size)
        self.rect = pygame.Rect(position[0], position[1], size[0], size[1])
        self.items: List[str] = []
        self.scroll_position = 0
        self.line_height = font_size + 4
        self.visible_lines = size[1] // self.line_height
        
    def update(self, items: List[str]):
        """Update the list items."""
        self.items = items
        self.scroll_position = min(self.scroll_position, 
                                 max(0, len(self.items) - self.visible_lines))
        
    def draw(self):
        """Draw the list on the screen."""
        pygame.draw.rect(self.screen, self.bg_color, self.rect)
        pygame.draw.rect(self.screen, self.text_color, self.rect, 2)
        
        for i, item in enumerate(self.items[self.scroll_position:]):
            if i * self.line_height < self.size[1] - self.line_height:
                text_surface = self.font.render(item, True, self.text_color)
                self.screen.blit(text_surface, 
                               (self.position[0] + 10, 
                                self.position[1] + 10 + i * self.line_height))
        
    def scroll_up(self):
        """Scroll the list up."""
        self.scroll_position = max(0, self.scroll_position - 1)
        
    def scroll_down(self):
        """Scroll the list down."""
        self.scroll_position = min(
            max(0, len(self.items) - self.visible_lines),
            self.scroll_position + 1
        )
