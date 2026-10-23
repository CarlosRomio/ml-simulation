"""Renderiza animais sem confundi-los com agentes humanos."""
import pygame
from animals.carnivore import Carnivore


class AnimalRenderer:
    def draw(self, screen, animal, *, camera_x: float, camera_y: float,
             cell_size: int, grid_x: int, grid_y: int, selected: bool = False) -> None:
        center=(grid_x+round((animal.x-camera_x)*cell_size)+cell_size//2,
                grid_y+round((animal.y-camera_y)*cell_size)+cell_size//2)
        radius=max(3,cell_size//3)
        color = ((207, 91, 77) if isinstance(animal, Carnivore) else (105, 195, 92)) if animal.alive else (100, 100, 100)
        # Silhueta quadrada arredondada para diferenciar animais dos agentes circulares.
        rect=pygame.Rect(center[0]-radius,center[1]-radius,radius*2,radius*2)
        if selected:
            outline = rect.inflate(max(4, cell_size // 3), max(4, cell_size // 3))
            pygame.draw.rect(screen, (245, 220, 90), outline, width=max(2, cell_size // 12),
                             border_radius=max(2, cell_size // 6))
        pygame.draw.rect(screen,color,rect,border_radius=max(1,cell_size//8))
        pygame.draw.rect(screen,(68,27,23) if isinstance(animal, Carnivore) else (25,45,25),rect,width=max(1,cell_size//18),border_radius=max(1,cell_size//8))
        if selected or cell_size >= 16:
            label = getattr(animal, "agent_id", "C?" if isinstance(animal, Carnivore) else "V?")
            font = pygame.font.SysFont("consolas", 11, bold=True)
            surface = font.render(label, True, (250, 245, 225))
            label_rect = surface.get_rect(midbottom=(center[0], center[1] - radius - 2))
            background = label_rect.inflate(4, 2)
            pygame.draw.rect(screen, (28, 34, 30), background, border_radius=2)
            screen.blit(surface, label_rect)
