import pygame

class PauseMenu:
	def __init__(self, screen, tts_engine, sound_manager):
		self.screen = screen
		self.tts_engine = tts_engine
		self.sound_manager = sound_manager
		self.options = ["Resume", "Settings", "Return to Main Menu"]
		self.selected_option = 0
		self.font = pygame.font.Font(None, 36)

	def handle_input(self, event):
		if event.type == pygame.KEYDOWN:
			if event.key == pygame.K_UP:
				self.selected_option = (self.selected_option - 1) % len(self.options)
				if self.tts_engine:
					self.tts_engine.output(self.options[self.selected_option])
			elif event.key == pygame.K_DOWN:
				self.selected_option = (self.selected_option + 1) % len(self.options)
				if self.tts_engine:
					self.tts_engine.output(self.options[self.selected_option])
			elif event.key == pygame.K_RETURN:
				selected = self.options[self.selected_option]
				if selected == "Resume":
					return "resume"
				elif selected == "Settings":
					return "settings"
				elif selected == "Return to Main Menu":
					return "menu"
			elif event.key == pygame.K_ESCAPE:
				return "resume"
		return None

	def render(self):
		# Semi-transparent background
		overlay = pygame.Surface(self.screen.get_size(), pygame.SRCALPHA)
		pygame.draw.rect(overlay, (0, 0, 0, 128), overlay.get_rect())
		self.screen.blit(overlay, (0, 0))

		# Draw menu title
		title = self.font.render("Game Paused", True, (255, 255, 255))
		title_rect = title.get_rect(center=(self.screen.get_width() // 2, 200))
		self.screen.blit(title, title_rect)

		# Draw menu options
		for i, option in enumerate(self.options):
			color = (255, 255, 0) if i == self.selected_option else (255, 255, 255)
			text = self.font.render(option, True, color)
			rect = text.get_rect(center=(self.screen.get_width() // 2, 300 + i * 50))
			self.screen.blit(text, rect)