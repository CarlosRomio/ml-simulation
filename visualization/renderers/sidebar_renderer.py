"""Painel compacto, com conteúdo rolável e métricas agrupadas."""

import pygame

from environment.resources import MaterialKind
from visualization.rendering_config import (
    CELL_COLOR,
    ENERGY_COLOR,
    ENERGY_LOW_COLOR,
    GRID_PADDING,
    GRID_COLOR,
    MUTED_COLOR,
    PANEL_COLOR,
    SIDEBAR_WIDTH,
    TEXT_COLOR,
)


class SidebarRenderer:
    """Renderiza um painel que se adapta à altura disponível.

    Cabeçalho e controles permanecem fixos. O conteúdo central pode ser
    rolado com a roda do mouse quando não couber na altura da janela.
    """

    HEADER_HEIGHT = 124
    FOOTER_HEIGHT = 112
    CONTENT_TOP = 132

    def __init__(self) -> None:
        self.title_font = pygame.font.SysFont("consolas", 21, bold=True)
        self.font = pygame.font.SysFont("consolas", 15)
        self.small_font = pygame.font.SysFont("consolas", 13)
        self.section_font = pygame.font.SysFont("consolas", 13, bold=True)
        self.scroll_offset = 0
        self.max_scroll = 0

    def scroll(self, amount: int) -> None:
        """Rola o painel; amount positivo move para conteúdo anterior."""
        self.scroll_offset = max(0, min(self.max_scroll, self.scroll_offset - amount * 28))

    def draw(
        self,
        screen: pygame.Surface,
        simulation,
        *,
        window_height: int,
        paused: bool,
        effective_speed: float,
        plant_counts: dict[str, int],
    ) -> None:
        sidebar = pygame.Rect(0, 0, SIDEBAR_WIDTH, window_height)
        pygame.draw.rect(screen, PANEL_COLOR, sidebar)

        self._draw_header(screen, simulation, paused)
        footer_top = max(self.HEADER_HEIGHT, window_height - self.FOOTER_HEIGHT)
        content_rect = pygame.Rect(
            0, self.CONTENT_TOP, SIDEBAR_WIDTH,
            max(0, footer_top - self.CONTENT_TOP - 8),
        )

        agent = simulation.observed_agent
        rows = self._build_rows(
            simulation, agent, effective_speed, plant_counts
        )
        content_height = self._measure_rows(rows)
        self.max_scroll = max(0, content_height - content_rect.height)
        self.scroll_offset = min(self.scroll_offset, self.max_scroll)

        old_clip = screen.get_clip()
        screen.set_clip(content_rect)
        y = content_rect.y - self.scroll_offset
        for item in rows:
            kind = item[0]
            if kind == "section":
                self._draw_section(screen, item[1], y)
                y += 23
            elif kind == "row":
                self._draw_row(screen, item[1], item[2], y, item[3] if len(item) > 3 else TEXT_COLOR)
                y += 21
            elif kind == "gap":
                y += item[1]
            elif kind == "bar":
                y = self._draw_bar(screen, item[1], item[2], item[3], item[4], y)
        screen.set_clip(old_clip)

        if self.max_scroll > 0:
            hint = "RODA DO MOUSE: ROLAR"
            self._text(screen, hint, footer_top - 17, self.small_font, MUTED_COLOR)
        self._draw_footer(screen, window_height, effective_speed)

    def _draw_header(self, screen, simulation, paused: bool) -> None:
        self._text(screen, "ML SIMULATION", 10, self.title_font)
        self._text(screen, "FLORESTA / SOBREVIVÊNCIA", 36, self.small_font, MUTED_COLOR)
        if not simulation.alive_agents and not simulation.alive_herbivores and not simulation.alive_carnivores:
            status, color = "POPULAÇÃO MORTA", ENERGY_LOW_COLOR
        elif paused:
            status, color = "PAUSADO", MUTED_COLOR
        else:
            status, color = "EXECUTANDO", ENERGY_COLOR
        status_width = self.small_font.size(status)[0]
        status_x = max(GRID_PADDING, SIDEBAR_WIDTH - GRID_PADDING - status_width)
        surface = self.small_font.render(status, True, color)
        screen.blit(surface, (status_x, 57))

        # Saúde e último dano ficam no cabeçalho fixo para não depender da rolagem.
        agent = simulation.observed_agent
        health_color = (225, 100, 85) if agent.health <= agent.needs.max_health * 0.3 else (105, 200, 125)
        health_label = self.small_font.render(
            f"SAÚDE {agent.agent_id or f'H{simulation.agents.index(agent) + 1:03d}'}: {agent.health:.1f}/{agent.needs.max_health:.0f}",
            True, TEXT_COLOR,
        )
        screen.blit(health_label, (GRID_PADDING, 73))
        health_bar = pygame.Rect(GRID_PADDING, 91, SIDEBAR_WIDTH - GRID_PADDING * 2, 8)
        pygame.draw.rect(screen, CELL_COLOR, health_bar)
        ratio = max(0.0, min(1.0, agent.health / agent.needs.max_health))
        if ratio > 0:
            pygame.draw.rect(screen, health_color, pygame.Rect(
                health_bar.x, health_bar.y, int(health_bar.width * ratio), health_bar.height
            ))
        pygame.draw.rect(screen, GRID_COLOR, health_bar, 1)

        recent = next((event for event in reversed(simulation.damage_events)
                       if event["target_id"] == id(agent)), None)
        if recent is None:
            damage_text = "Último dano: nenhum registrado"
            damage_color = MUTED_COLOR
        else:
            shelter_label = "dentro do abrigo" if recent["sheltered"] else "fora do abrigo"
            damage_text = f"Último dano: -{recent['damage']:.1f} HP ({shelter_label})"
            damage_color = (245, 170, 120)
        self._text(screen, damage_text, 103, self.small_font, damage_color)
        pygame.draw.line(screen, GRID_COLOR, (GRID_PADDING, 119),
                         (SIDEBAR_WIDTH - GRID_PADDING, 119), 1)

    def _build_rows(self, simulation, agent, effective_speed, plant_counts):
        rows = []
        alive_humans = len(simulation.alive_agents)
        alive_herbivores = len(simulation.alive_herbivores)
        alive_carnivores = len(simulation.alive_carnivores)
        water_count = len(simulation.world.get_water_positions())
        decision_trace = agent.last_decision_trace or {}
        decision_score = decision_trace.get("score")
        decision_alternatives = decision_trace.get("alternatives", [])
        rows.extend([
            ("section", "MUNDO"),
            ("row", "Passos", str(simulation.steps)),
            ("row", "Humanos vivos", f"{alive_humans}/{len(simulation.agents)}"),
            ("row", "Herbívoros vivos", f"{alive_herbivores}/{len(simulation.herbivores)}", (126, 210, 112)),
            ("row", "Carnívoros vivos", f"{alive_carnivores}/{len(simulation.carnivores)}", (220, 120, 105)),
            ("row", "Fontes de água", str(water_count), (90, 190, 235)),
            ("gap", 5),
            ("section", "VEGETAÇÃO"),
            ("row", "Plantas totais", str(plant_counts.get("total", 0))),
            ("row", "Sementes", str(plant_counts.get("seeds", 0))),
            ("row", "Em crescimento", str(plant_counts.get("growing", 0))),
            ("row", "Maduras", str(plant_counts.get("mature", 0))),
            ("row", "Coleta humana", str(sum(m.food_collected for m in simulation.metrics_by_agent.values()))),
            ("gap", 5),
            ("section", "INVENTÁRIO DO AGENTE"),
            ("row", "Alimento", f"{agent.inventory.food_quantity:g}"),
            ("row", "Madeira", f"{agent.inventory.quantity_of(MaterialKind.WOOD):g}"),
            ("row", "Pedra", f"{agent.inventory.quantity_of(MaterialKind.STONE):g}"),
            ("row", "Fibra", f"{agent.inventory.quantity_of(MaterialKind.FIBER):g}"),
            ("row", "Carga / capacidade", f"{agent.inventory.current_weight:g} / {agent.inventory.capacity_weight:g}"),
            ("gap", 5),
            ("section", "ABRIGOS E ARMAZENAMENTO"),
            ("row", "Abrigos / depósitos", str(len(simulation.world.get_storage_positions()))),
            ("row", "Alimento", f"{simulation.world.get_storage_counts()['storage_food_units']:g}"),
            ("row", "Madeira", f"{simulation.world.get_storage_counts()['storage_wood_units']:g}"),
            ("row", "Pedra", f"{simulation.world.get_storage_counts()['storage_stone_units']:g}"),
            ("row", "Peso armazenado", f"{simulation.world.get_storage_counts()['storage_weight']:g} / {simulation.world.get_storage_counts()['storage_capacity_weight']:g}"),
            ("gap", 5),
            ("section", f"AGENTE {agent.agent_id or f'H{simulation.agents.index(agent) + 1:03d}'}"),
            ("row", "Estado", "VIVO" if agent.alive else "MORTO",
             ENERGY_COLOR if agent.alive else ENERGY_LOW_COLOR),
            ("row", "Controle", "MANUAL" if simulation.manual_control_agent is agent else "IA",
             (245, 220, 90) if simulation.manual_control_agent is agent else MUTED_COLOR),
            ("section", "PERSONALIDADE"),
            ("row", "Curiosidade", f"{agent.personality.curiosity:.2f}"),
            ("row", "Aversão ao risco", f"{agent.personality.risk_aversion:.2f}"),
            ("row", "Sociabilidade", f"{agent.personality.sociability:.2f}"),
            ("row", "Agressividade", f"{agent.personality.aggressiveness:.2f}"),
            ("row", "Persistência", f"{agent.personality.persistence:.2f}"),
            ("row", "Sensib. recompensa", f"{agent.personality.reward_sensitivity:.2f}"),
            ("section", "DECISÃO"),
            ("row", "Intenção atual", str(agent.last_behavior_intent)),
            ("row", "Última ação avaliada", str(
                decision_trace.get("intent", "prioridade comportamental")
            )),
            ("row", "Valor da decisão", f"{float(decision_score):.2f}" if decision_score is not None else "—"),
            ("row", "Alternativas comparadas", str(len(decision_alternatives))),
            ("section", "SOCIAL"),
            ("row", "Humanos próximos (3)", str(sum(
                1 for other in simulation.alive_agents if other is not agent
                and abs(other.x - agent.x) + abs(other.y - agent.y) <= 3
            ))),
            ("row", "Relações (afinidade >= 0,2)", str(sum(value >= 0.2 for value in agent.social_affinities.values()))),
            *self._social_relationship_rows(agent, simulation),
            ("bar", "Saúde", agent.health, agent.needs.max_health,
             (225, 100, 85) if agent.health <= agent.needs.max_health * 0.3 else (105, 200, 125)),
            ("bar", "Estamina", agent.energy, agent.max_energy, ENERGY_COLOR),
            ("bar", "Fome", agent.hunger, agent.needs.max_hunger,
             (225, 100, 85) if agent.hunger >= agent.needs.starvation_threshold else (220, 170, 80)),
            ("bar", "Sede", agent.thirst, agent.needs.max_thirst,
             (225, 100, 85) if agent.thirst >= agent.needs.dehydration_threshold else (90, 190, 235)),
            ("gap", 5),
            ("gap", 5),
            ("section", "DANO / COMBATE"),
            ("row", "Dano por predação", f"{agent.needs.damage_by_cause.get('PREDATION', 0.0):.1f}"),
            ("row", "Dano por fome", f"{agent.needs.damage_by_cause.get('STARVATION', 0.0):.1f}"),
            ("row", "Dano por sede", f"{agent.needs.damage_by_cause.get('DEHYDRATION', 0.0):.1f}"),
            ("section", "ÚLTIMOS ATAQUES"),
            *self._recent_damage_rows(simulation, agent),
            ("gap", 5),
            ("section", "INTERAÇÕES"),
            ("row", "Ataques", str(simulation.attacks)),
            ("row", "Ataques de carnívoros", str(simulation.carnivore_attacks)),
            ("row", "Caças concluídas", str(simulation.animals_killed)),
        ])
        return rows

    @staticmethod
    def _social_relationship_rows(agent, simulation):
        if not agent.social_affinities:
            return [("row", "Afinidades", "ainda sem histórico", MUTED_COLOR)]
        names = {other.agent_id: other for other in simulation.agents}
        ranked = sorted(agent.social_affinities.items(), key=lambda item: (-item[1], item[0]))[:3]
        return [
            ("row", f"Afinidade {other_id}", f"{affinity:.2f}",
             (125, 205, 150) if affinity >= 0.2 else MUTED_COLOR)
            for other_id, affinity in ranked if other_id in names
        ]

    @staticmethod
    def _recent_damage_rows(simulation, agent):
        events = [
            event for event in simulation.damage_events
            if event["target_id"] == id(agent)
        ][-3:]
        if not events:
            return [("row", "Sem dano registrado", "—", MUTED_COLOR)]
        rows = []
        for event in reversed(events):
            location = "abrigo" if event["sheltered"] else "fora"
            rows.append((
                "row",
                f"Passo {event['step']} ({location})",
                f"-{event['damage']:.1f} HP",
                (225, 100, 85),
            ))
        return rows

    @staticmethod
    def _measure_rows(rows) -> int:
        height = 0
        for item in rows:
            if item[0] == "section":
                height += 23
            elif item[0] == "row":
                height += 21
            elif item[0] == "bar":
                height += 48
            else:
                height += item[1]
        return height

    def _draw_section(self, screen, label: str, y: int) -> None:
        self._text(screen, label, y, self.section_font, MUTED_COLOR)
        pygame.draw.line(screen, GRID_COLOR, (GRID_PADDING, y + 17),
                         (SIDEBAR_WIDTH - GRID_PADDING, y + 17), 1)

    def _draw_row(self, screen, label: str, value: str, y: int, color) -> None:
        self._text(screen, label, y, self.small_font, MUTED_COLOR)
        value_surface = self.small_font.render(value, True, color)
        x = SIDEBAR_WIDTH - GRID_PADDING - value_surface.get_width()
        screen.blit(value_surface, (max(GRID_PADDING + 85, x), y))

    def _draw_bar(self, screen, label: str, value: float, maximum: float, color, y: int) -> int:
        maximum = max(1.0, float(maximum))
        ratio = max(0.0, min(1.0, float(value) / maximum))
        self._text(screen, label, y, self.small_font, MUTED_COLOR)
        # O valor fica alinhado à direita na mesma linha do rótulo.
        value_surface = self.small_font.render(f"{value:.1f}/{maximum:.0f}", True, TEXT_COLOR)
        screen.blit(value_surface, (SIDEBAR_WIDTH - GRID_PADDING - value_surface.get_width(), y))
        bar = pygame.Rect(GRID_PADDING, y + 21, SIDEBAR_WIDTH - GRID_PADDING * 2, 9)
        pygame.draw.rect(screen, CELL_COLOR, bar)
        if ratio > 0:
            pygame.draw.rect(screen, color, pygame.Rect(bar.x, bar.y, int(bar.width * ratio), bar.height))
        pygame.draw.rect(screen, GRID_COLOR, bar, 1)
        return y + 48

    def _draw_footer(self, screen, window_height: int, effective_speed: float) -> None:
        top = max(self.HEADER_HEIGHT, window_height - self.FOOTER_HEIGHT)
        pygame.draw.rect(screen, PANEL_COLOR, pygame.Rect(0, top, SIDEBAR_WIDTH, window_height - top))
        pygame.draw.line(screen, GRID_COLOR, (GRID_PADDING, top),
                         (SIDEBAR_WIDTH - GRID_PADDING, top), 1)
        self._text(screen, "VELOCIDADE", top + 6, self.small_font, MUTED_COLOR)
        self._text(screen, f"{effective_speed:g} passos/s", top + 22, self.font)
        self._text(screen, "1 Normal | 2 Rápido | 3 Turbo", top + 42, self.small_font)
        self._text(screen, "M Manual | WASD / Setas", top + 62, self.small_font)
        self._text(screen, "B Abrigo | F Predador teste", top + 81, self.small_font)
        self._text(screen, "Espaço Pausa | ESC Sair", top + 98, self.small_font)

    @staticmethod
    def _text(
        screen: pygame.Surface,
        text: str,
        y: int,
        selected_font: pygame.font.Font | None = None,
        color: tuple[int, int, int] = TEXT_COLOR,
    ) -> None:
        if selected_font is None:
            selected_font = pygame.font.SysFont("consolas", 15)
        surface = selected_font.render(text, True, color)
        screen.blit(surface, (GRID_PADDING, y))
