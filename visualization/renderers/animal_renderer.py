"""Renderiza animais sem confundi-los com agentes humanos."""
import pygame
from animals.carnivore import Carnivore


class AnimalRenderer:
    def draw(self, screen, animal, *, camera_x: float, camera_y: float,
             cell_size: int, grid_x: int, grid_y: int) -> None:
        center=(grid_x+round((animal.x-camera_x)*cell_size)+cell_size//2,
                grid_y+round((animal.y-camera_y)*cell_size)+cell_size//2)
        radius=max(3,cell_size//3)
        color = ((207, 91, 77) if isinstance(animal, Carnivore) else (105, 195, 92)) if animal.alive else (100, 100, 100)
        # Silhueta quadrada arredondada para diferenciar animais dos agentes circulares.
        rect=pygame.Rect(center[0]-radius,center[1]-radius,radius*2,radius*2)
        pygame.draw.rect(screen,color,rect,border_radius=max(1,cell_size//8))
        pygame.draw.rect(screen,(68,27,23) if isinstance(animal, Carnivore) else (25,45,25),rect,width=max(1,cell_size//18),border_radius=max(1,cell_size//8))
