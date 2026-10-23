"""Loop principal da interface Pygame.

A coordenação de eventos permanece aqui nesta primeira etapa. O desenho foi
extraído para renderizadores independentes para preparar a câmera e múltiplos
agentes sem reescrever a renderização do mundo.
"""

import pygame

from simulation.simulation import Simulation
from visualization.camera import Camera
from visualization.rendering_config import (
    BACKGROUND,
    BASE_SPEED,
    GRID_PADDING,
    MAX_CELL_SIZE,
    MAX_GRID_SIZE,
    MIN_CELL_SIZE,
    SIDEBAR_WIDTH,
    SPEED_MULTIPLIERS,
    VIEW_HEIGHT,
    VIEW_WIDTH,
)
from visualization.renderers.agent_renderer import AgentRenderer
from visualization.renderers.animal_renderer import AnimalRenderer
from visualization.renderers.sidebar_renderer import SidebarRenderer
from visualization.renderers.world_renderer import WorldRenderer


def run(simulation: Simulation) -> None:
    pygame.init()
    world = simulation.world

    view_width = min(VIEW_WIDTH, world.width)
    view_height = min(VIEW_HEIGHT, world.height)
    # Janela inicial compacta, mas redimensionável. A área do mundo passa a
    # acompanhar o tamanho da janela em vez de impor uma grade em pixels fixa.
    window_width, window_height = 1100, 700
    grid_x = SIDEBAR_WIDTH + GRID_PADDING * 2
    grid_y = GRID_PADDING
    grid_width = max(1, window_width - grid_x - GRID_PADDING)
    grid_height = max(1, window_height - grid_y - GRID_PADDING)
    cell_size = max(MIN_CELL_SIZE, min(30, MAX_CELL_SIZE,
                                       MAX_GRID_SIZE // view_width,
                                       MAX_GRID_SIZE // view_height))

    screen = pygame.display.set_mode((window_width, window_height), pygame.RESIZABLE)
    pygame.display.set_caption("ML Simulation - Survival")
    clock = pygame.time.Clock()

    world_renderer = WorldRenderer()
    agent_renderer = AgentRenderer()
    animal_renderer = AnimalRenderer()
    sidebar_renderer = SidebarRenderer()
    camera = Camera(world.width, world.height, view_width, view_height)
    camera.configure_viewport(grid_width, grid_height, cell_size)
    grid_viewport = pygame.Rect(grid_x, grid_y, grid_width, grid_height)
    dragging_camera = False
    last_mouse_position: tuple[int, int] | None = None
    mouse_down_position: tuple[int, int] | None = None

    running = True
    paused = False
    accumulated_time = 0.0
    simulation_speed = 1
    build_message = ""

    while running:
        elapsed_ms = clock.tick(60)

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.VIDEORESIZE:
                # Impõe um mínimo para manter painel e controles utilizáveis.
                new_width = max(800, event.w)
                new_height = max(480, event.h)
                screen = pygame.display.set_mode((new_width, new_height), pygame.RESIZABLE)
                window_width, window_height = screen.get_size()
                grid_width = max(1, window_width - grid_x - GRID_PADDING)
                grid_height = max(1, window_height - grid_y - GRID_PADDING)
                grid_viewport = pygame.Rect(grid_x, grid_y, grid_width, grid_height)
                camera.configure_viewport(grid_width, grid_height, camera.cell_size)
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                if grid_viewport.collidepoint(event.pos):
                    dragging_camera = True
                    last_mouse_position = event.pos
                    mouse_down_position = event.pos
            elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
                if mouse_down_position is not None and abs(event.pos[0] - mouse_down_position[0]) <= 5 and abs(event.pos[1] - mouse_down_position[1]) <= 5 and grid_viewport.collidepoint(event.pos):
                    selected_position = camera.screen_to_world(event.pos[0], event.pos[1], grid_x, grid_y)
                    selectable = simulation.agents + simulation.herbivores + simulation.carnivores
                    selected = next((item for item in selectable
                                     if item.alive and (item.x, item.y) == selected_position), None)
                    if selected is not None:
                        simulation.observed_individual = selected
                        # Apenas humanos podem ser controlados manualmente ou usados
                        # pelas ações de construção do protótipo atual.
                        if selected in simulation.agents:
                            simulation.observed_agent = selected
                            if simulation.manual_control_agent is not None:
                                simulation.set_manual_control(selected, True)
                        elif simulation.manual_control_agent is not None:
                            # Ao inspecionar um animal, não deixa o teclado continuar
                            # controlando silenciosamente um humano não selecionado.
                            simulation.set_manual_control(simulation.manual_control_agent, False)
                dragging_camera = False
                last_mouse_position = None
                mouse_down_position = None
            elif event.type == pygame.MOUSEWHEEL:
                mouse_position = pygame.mouse.get_pos()
                if mouse_position[0] < SIDEBAR_WIDTH:
                    sidebar_renderer.scroll(event.y)
                elif grid_viewport.collidepoint(mouse_position):
                    zoom_step = 3 if event.y > 0 else -3
                    new_cell_size = max(
                        MIN_CELL_SIZE,
                        min(MAX_CELL_SIZE, camera.cell_size + zoom_step),
                    )
                    if new_cell_size != camera.cell_size:
                        camera.zoom_at(
                            mouse_position[0],
                            mouse_position[1],
                            grid_x,
                            grid_y,
                            new_cell_size,
                        )
            elif event.type == pygame.MOUSEMOTION and dragging_camera:
                if last_mouse_position is not None:
                    dx = event.pos[0] - last_mouse_position[0]
                    dy = event.pos[1] - last_mouse_position[1]
                    camera.pan_pixels(dx, dy)
                last_mouse_position = event.pos
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    running = False
                elif event.key == pygame.K_SPACE and (bool(simulation.alive_agents) or bool(simulation.alive_herbivores) or bool(simulation.alive_carnivores)):
                    paused = not paused
                elif event.key == pygame.K_b:
                    if simulation.observed_individual in simulation.agents:
                        built = simulation.build_shelter(simulation.observed_agent)
                        build_message = ("Abrigo construído" if built else
                                         "Abrigo: requer 5 madeiras, 2 pedras e celula livre")
                    else:
                        build_message = "Construção disponível apenas para humanos"
                elif event.key == pygame.K_f:
                    if simulation.observed_individual in simulation.agents:
                        test_carnivore = simulation.spawn_test_carnivore_near(
                            simulation.observed_agent
                        )
                        build_message = (
                            "Predador de teste criado ao lado do humano"
                            if test_carnivore is not None
                            else "Predador de teste: nenhuma celula adjacente livre"
                        )
                    else:
                        build_message = "Predador de teste: selecione um humano"
                elif event.key == pygame.K_m:
                    if simulation.observed_individual not in simulation.agents:
                        build_message = "Controle manual disponível apenas para humanos"
                    elif simulation.manual_control_agent is simulation.observed_agent:
                        simulation.set_manual_control(simulation.observed_agent, False)
                        build_message = "Controle manual desativado; agente voltou a IA"
                    elif simulation.set_manual_control(simulation.observed_agent, True):
                        build_message = "Controle manual: WASD/setas; segure Shift para correr"
                    else:
                        build_message = "Nao foi possivel controlar um agente morto"
                elif event.key in (pygame.K_UP, pygame.K_w):
                    simulation.queue_manual_action(0, -1, run=bool(pygame.key.get_mods() & pygame.KMOD_SHIFT))
                elif event.key in (pygame.K_DOWN, pygame.K_s):
                    simulation.queue_manual_action(0, 1, run=bool(pygame.key.get_mods() & pygame.KMOD_SHIFT))
                elif event.key in (pygame.K_LEFT, pygame.K_a):
                    simulation.queue_manual_action(-1, 0, run=bool(pygame.key.get_mods() & pygame.KMOD_SHIFT))
                elif event.key in (pygame.K_RIGHT, pygame.K_d):
                    simulation.queue_manual_action(1, 0, run=bool(pygame.key.get_mods() & pygame.KMOD_SHIFT))
                elif event.key == pygame.K_1:
                    simulation_speed = 1
                elif event.key == pygame.K_2:
                    simulation_speed = 2
                elif event.key == pygame.K_3:
                    simulation_speed = 3

        effective_speed = BASE_SPEED * SPEED_MULTIPLIERS[simulation_speed]
        if not paused and (bool(simulation.alive_agents) or bool(simulation.alive_herbivores) or bool(simulation.alive_carnivores)):
            accumulated_time += elapsed_ms * effective_speed
            while accumulated_time >= 1000:
                simulation.step()
                accumulated_time -= 1000
                if not (bool(simulation.alive_agents) or bool(simulation.alive_herbivores) or bool(simulation.alive_carnivores)):
                    accumulated_time = 0.0
                    break

        window_width, window_height = screen.get_size()
        screen.fill(BACKGROUND)
        agent = simulation.observed_individual

        # A câmera é independente da posição do agente e se move por arraste.
        camera_x = camera.x
        camera_y = camera.y
        cell_size = camera.cell_size
        visible_world_width = camera.visible_width
        visible_world_height = camera.visible_height

        visible_cells = simulation.perception.observe(
            world, agent.x, agent.y, radius=agent.vision_radius
        )
        visible_positions = {(cell.x, cell.y) for cell in visible_cells}
        plant_counts = world.get_plant_counts()

        sidebar_renderer.draw(
            screen,
            simulation,
            window_height=window_height,
            paused=paused,
            effective_speed=effective_speed,
            plant_counts=plant_counts,
        )
        world_renderer.draw(
            screen,
            world,
            camera_x=camera_x,
            camera_y=camera_y,
            view_width=visible_world_width,
            view_height=visible_world_height,
            cell_size=cell_size,
            grid_x=grid_x,
            grid_y=grid_y,
            viewport_width_px=grid_width,
            viewport_height_px=grid_height,
            visible_positions=visible_positions,
        )
        previous_clip = screen.get_clip()
        screen.set_clip(grid_viewport)
        try:
            for current_agent in simulation.agents:
                # Evita desenhar agentes fora da região visível.
                if not (
                    camera_x <= current_agent.x < camera_x + visible_world_width
                    and camera_y <= current_agent.y < camera_y + visible_world_height
                ):
                    continue
                agent_renderer.draw(
                    screen,
                    current_agent,
                    camera_x=camera_x,
                    camera_y=camera_y,
                    cell_size=cell_size,
                    grid_x=grid_x,
                    grid_y=grid_y,
                    selected=current_agent is simulation.observed_individual,
                )
            for animal in (*simulation.herbivores, *simulation.carnivores):
                if not (camera_x <= animal.x < camera_x + visible_world_width and
                        camera_y <= animal.y < camera_y + visible_world_height):
                    continue
                animal_renderer.draw(screen, animal, camera_x=camera_x, camera_y=camera_y,
                                     cell_size=cell_size, grid_x=grid_x, grid_y=grid_y,
                                     selected=animal is simulation.observed_individual)
        finally:
            screen.set_clip(previous_clip)
        if build_message:
            font = pygame.font.SysFont("consolas", 16)
            notice = font.render(build_message, True, (245, 236, 212))
            screen.blit(notice, (grid_x + 8, window_height - 28))
        pygame.display.flip()

    pygame.quit()
