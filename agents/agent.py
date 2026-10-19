import random

from random import Random
from collections.abc import Callable

from environment.cell import Cell
from environment.world import World
from agents.navigation.bfs import find_path
from agents.needs import AgentNeeds
from environment.resources import MaterialKind, MaterialResource, Water, Plant, Food
from environment.storage import Storage
from environment.shelter import Shelter
from agents.inventory import Inventory
from agents.species import Species


Position = tuple[int, int]

Pathfinder = Callable[
    [World, Position, Position],
    list[Position] | None,
]


class Agent:
    def __init__(
        self,
        x: int,
        y: int,
        max_energy: float = 100.0,
        vision_radius: int = 4,
        rng: Random | None = None,
        needs: AgentNeeds | None = None,
        species: Species = Species.HUMAN,
        inventory: Inventory | None = None,
        sociability: float = 0.5,
        agent_id: str | None = None,
    ):
        if vision_radius < 0:
            raise ValueError("vision_radius não pode ser negativo")

        self.x = x
        self.y = y
        # Identificador legível, atribuído pela simulação se não for fornecido.
        self.agent_id = agent_id
        self.species = Species(species)
        self.hunt_target: Position | None = None
        self.running = False

        self.target: Position | None = None
        self.path: list[Position] = []

        self.needs = needs if needs is not None else AgentNeeds(
            max_energy=max_energy,
            energy=max_energy,
        )
        self.alive = self.needs.alive

        self.vision_radius = vision_radius
        self.visit_counts: dict[Position, int] = {}

        self.rng = rng if rng is not None else random
        self.inventory = inventory if inventory is not None else Inventory()
        if not 0.0 <= sociability <= 1.0:
            raise ValueError("A sociabilidade deve estar entre 0 e 1.")
        # Traço estável por indivíduo; não muda a cada passo da simulação.
        self.sociability = float(sociability)
        # Posições de humanos vivos dentro do alcance social percebido neste passo.
        self.social_neighbors: list[Position] = []
        # Afinidades persistentes por identificador de indivíduo (0..1).
        self.social_affinities: dict[str, float] = {}
        # Afinidades dos humanos visíveis neste passo, indexadas por posição.
        self.social_neighbor_affinities: dict[Position, float] = {}
        # Estado de intenção usado pela política autônoma e resolvido pela simulação.
        self.building_intent = False
        self.occupied_positions: set[Position] = set()
        self.unavailable_shelter_positions: set[Position] = set()

    @property
    def max_energy(self) -> float:
        return self.needs.max_energy

    @max_energy.setter
    def max_energy(self, value: float) -> None:
        self.needs.max_energy = value
        self.needs.energy = min(self.needs.energy, value)

    @property
    def energy(self) -> float:
        return self.needs.energy

    @energy.setter
    def energy(self, value: float) -> None:
        self.needs.energy = max(0.0, min(self.needs.max_energy, value))

    @property
    def health(self) -> float:
        return self.needs.health

    @property
    def hunger(self) -> float:
        return self.needs.hunger

    @property
    def thirst(self) -> float:
        return self.needs.thirst

    def rest(self, amount: float = 5.0) -> None:
        if self.alive:
            self.needs.restore_energy(amount)

    def consume_energy(self, amount: float = 1.0) -> None:
        if amount < 0:
            raise ValueError("O consumo de energia não pode ser negativo.")
        if not self.alive:
            return

        self.energy = max(0.0, self.energy - amount)

        # Energia é estamina: chegar a zero impede corrida, mas não mata.

    def eat(self, amount: float) -> None:
        if not self.alive:
            return

        self.needs.eat(amount)
        self.needs.restore_energy(amount * 0.6)

    def can_collect_resource(self, resource: object) -> bool:
        if not getattr(resource, "is_collectible", False):
            return False
        if isinstance(resource, MaterialResource):
            return self.inventory.max_collectible_units(resource.kind) >= 1
        if isinstance(resource, Plant):
            return self.inventory.max_food_units() >= 1
        if isinstance(resource, Food):
            return self.inventory.available_weight >= 1e-9
        return True

    def _clear_target(self) -> None:
        self.target = None
        self.path.clear()

    @staticmethod
    def _shelter_positions(world: World) -> list[Position]:
        return [
            (cell.x, cell.y)
            for row in world.grid for cell in row
            if isinstance(cell.structure, Shelter)
        ]

    def _has_nearby_shelter(
        self, position: Position, world: World, radius: int = 8,
        shelter_positions: list[Position] | None = None,
    ) -> bool:
        x, y = position
        shelters = shelter_positions if shelter_positions is not None else self._shelter_positions(world)
        return any(abs(sx - x) + abs(sy - y) <= radius for sx, sy in shelters)

    def _select_target(
        self,
        nearby_cells: list[Cell],
        world: World,
        pathfinder: Pathfinder,
    ) -> None:
        current_position = (self.x, self.y)
        self.building_intent = False

        if self.hunt_target is not None:
            path = pathfinder(world, current_position, self.hunt_target)
            if path is not None and len(path) > 1:
                self.target = self.hunt_target
                self.path = path
                return
            self.hunt_target = None

        shelter_positions = self._shelter_positions(world)
        nearby_shelter = self._has_nearby_shelter(
            current_position, world, shelter_positions=shelter_positions
        )
        wood = self.inventory.quantity_of(MaterialKind.WOOD)
        stone = self.inventory.quantity_of(MaterialKind.STONE)
        has_building_materials = wood >= 5 and stone >= 2

        # Se já possui os materiais, procura um local livre afastado de outros
        # abrigos. Isso evita estruturas sobre recursos, obstáculos ou agentes.
        # O raio limitado mantém a escolha de destino barata por passo.
        if has_building_materials and not nearby_shelter and self.hunger < 35.0 and self.thirst < 40.0:
            build_sites: list[Position] = []
            search_radius = 10
            for y in range(max(0, self.y - search_radius), min(world.height, self.y + search_radius + 1)):
                for x in range(max(0, self.x - search_radius), min(world.width, self.x + search_radius + 1)):
                    position = (x, y)
                    if abs(x - self.x) + abs(y - self.y) > search_radius:
                        continue
                    if position in self.occupied_positions:
                        continue
                    cell = world.get_cell(x, y)
                    if cell.obstacle is not None or cell.resource is not None or cell.structure is not None:
                        continue
                    if self._has_nearby_shelter(
                        position, world, shelter_positions=shelter_positions
                    ):
                        continue
                    build_sites.append(position)
            build_sites.sort(key=lambda pos: abs(pos[0] - self.x) + abs(pos[1] - self.y))
            for candidate in build_sites:
                path = pathfinder(world, current_position, candidate)
                if path is None:
                    continue
                self.building_intent = True
                self.target = candidate
                self.path = path
                return

        # Se estiver cansado e sem necessidades urgentes, procura um abrigo
        # compartilhado que não esteja ocupado por outro humano.
        if self.energy < 50.0 and self.hunger < 35.0 and self.thirst < 40.0:
            shelters = [
                (cell.x, cell.y)
                for row in world.grid for cell in row
                if isinstance(cell.structure, Shelter)
                and (cell.x, cell.y) not in self.unavailable_shelter_positions
                and (cell.x, cell.y) != current_position
            ]
            shelters.sort(key=lambda pos: abs(pos[0] - self.x) + abs(pos[1] - self.y))
            for candidate in shelters:
                path = pathfinder(world, current_position, candidate)
                if path is not None and len(path) > 1:
                    self.target = candidate
                    self.path = path
                    return

        # Se não existe abrigo próximo, coleta por iniciativa própria os
        # materiais que faltam para construir. Necessidades fisiológicas mais
        # urgentes continuam tendo prioridade.
        should_gather_building_materials = (
            not nearby_shelter and not has_building_materials
            and self.hunger < 25.0 and self.thirst < 25.0
            and self.energy > 15.0
        )
        if should_gather_building_materials:
            needed_kinds = []
            if wood < 5:
                needed_kinds.append(MaterialKind.WOOD)
            if stone < 2:
                needed_kinds.append(MaterialKind.STONE)
            # Prioriza madeira, que exige mais unidades, e passa para pedra
            # assim que a quantidade de madeira necessária estiver completa.
            needed_kinds.sort(key=lambda kind: 0 if kind == MaterialKind.WOOD and wood < 5 else 1)
            for kind in needed_kinds:
                candidates = [
                    (cell.x, cell.y)
                    for row in world.grid for cell in row
                    if isinstance(cell.resource, MaterialResource)
                    and cell.resource.kind == kind
                    and self.can_collect_resource(cell.resource)
                    and (cell.x, cell.y) != current_position
                ]
                candidates.sort(key=lambda pos: abs(pos[0] - self.x) + abs(pos[1] - self.y))
                for candidate in candidates:
                    path = pathfinder(world, current_position, candidate)
                    if path is not None and len(path) > 1:
                        self.target = candidate
                        self.path = path
                        return

        # Sociabilidade é uma preferência de baixa prioridade: só influencia a
        # decisão quando o agente não está com fome/sede relevantes, não está
        # construindo e tem energia para se deslocar. O alvo é uma célula livre
        # próxima de outro humano, nunca a própria célula ocupada por ele.
        if (
            self.sociability >= 0.35
            and self.hunger < 25.0
            and self.thirst < 25.0
            and self.energy > 25.0
            and self.social_neighbors
        ):
            # Entre indivíduos visíveis, prefere aqueles com maior afinidade
            # acumulada; em empate, favorece quem está mais próximo.
            nearest_neighbor = max(
                self.social_neighbors,
                key=lambda pos: (
                    self.social_neighbor_affinities.get(pos, 0.0),
                    -(abs(pos[0] - self.x) + abs(pos[1] - self.y)),
                    -pos[1], -pos[0],
                ),
            )
            neighbor_distance = abs(nearest_neighbor[0] - self.x) + abs(nearest_neighbor[1] - self.y)
            preferred_distance = 1 if self.sociability >= 0.75 else (2 if self.sociability >= 0.5 else 3)
            # Se já está numa distância social razoável, não persegue outro
            # indivíduo: pode continuar explorando e evita formar uma pilha.
            # Estar perto de um desconhecido não substitui automaticamente
            # uma relação preferida: a proximidade só satisfaz a intenção social
            # quando o indivíduo selecionado como alvo já está perto.
            already_socially_close = neighbor_distance <= preferred_distance
            if not already_socially_close and neighbor_distance > preferred_distance:
                candidates: list[Position] = []
                for y in range(max(0, nearest_neighbor[1] - preferred_distance),
                               min(world.height, nearest_neighbor[1] + preferred_distance + 1)):
                    for x in range(max(0, nearest_neighbor[0] - preferred_distance),
                                   min(world.width, nearest_neighbor[0] + preferred_distance + 1)):
                        candidate = (x, y)
                        if candidate == nearest_neighbor or candidate == current_position:
                            continue
                        if abs(x - nearest_neighbor[0]) + abs(y - nearest_neighbor[1]) != preferred_distance:
                            continue
                        if candidate in self.occupied_positions:
                            continue
                        cell = world.get_cell(x, y)
                        if cell.obstacle is not None or cell.resource is not None or cell.structure is not None:
                            continue
                        candidates.append(candidate)
                candidates.sort(key=lambda pos: (
                    abs(pos[0] - self.x) + abs(pos[1] - self.y),
                    pos[1], pos[0],
                ))
                for candidate in candidates:
                    path = pathfinder(world, current_position, candidate)
                    if path is not None and len(path) > 1:
                        self.target = candidate
                        self.path = path
                        return

        # Necessidades competem por prioridade: água crítica, comida e água
        # preventiva. A coleta de materiais entra depois dessas necessidades.
        target_groups: list[list[Position]] = []
        if self.thirst >= 40.0:
            target_groups.append(world.get_water_positions())
        food_positions = [
            (cell.x, cell.y)
            for row in world.grid
            for cell in row
            if cell.resource is not None
            and not isinstance(cell.resource, MaterialResource)
            and self.can_collect_resource(cell.resource)
            and (cell.x, cell.y) != current_position
        ]
        target_groups.append(food_positions)
        if 25.0 <= self.thirst < 40.0:
            target_groups.append(world.get_water_positions())

        for candidates in target_groups:
            candidates = list(candidates)
            self.rng.shuffle(candidates)
            candidates.sort(
                key=lambda position: abs(position[0] - self.x) + abs(position[1] - self.y)
            )
            for candidate in candidates:
                path = pathfinder(world, current_position, candidate)
                if path is not None and len(path) > 1:
                    self.target = candidate
                    self.path = path
                    return

        self._clear_target()

    def choose_action(
        self,
        nearby_cells: list[Cell],
        world: World,
        pathfinder: Pathfinder = find_path,
    ) -> Position:
        self._record_position()
        current_position = (self.x, self.y)
        current_cell = world.get_cell(*current_position)
        # Um abrigo passa a ter utilidade prática: um humano cansado pode
        # interromper a exploração para recuperar estamina, desde que fome e
        # sede não exijam atenção prioritária.
        if (
            isinstance(current_cell.structure, Shelter)
            and self.energy < 70.0
            and self.hunger < 35.0
            and self.thirst < 40.0
        ):
            self._clear_target()
            return (0, 0)

        if self.thirst >= 1.0 and isinstance(current_cell.resource, Water):
            return (0, 0)

        current_resource = current_cell.resource
        if isinstance(current_resource, MaterialResource) and self.can_collect_resource(current_resource):
            # Continua coletando enquanto precisa dos materiais; quando já pode
            # construir longe de outro abrigo, deixa o depósito para o local de obra.
            wood = self.inventory.quantity_of(MaterialKind.WOOD)
            stone = self.inventory.quantity_of(MaterialKind.STONE)
            has_building_materials = wood >= 5 and stone >= 2
            material_still_needed = (
                (current_resource.kind == MaterialKind.WOOD and wood < 5)
                or (current_resource.kind == MaterialKind.STONE and stone < 2)
            )
            if material_still_needed:
                return (0, 0)
            if self._has_nearby_shelter(current_position, world):
                # Próximo de um abrigo, coleta de materiais é oportunista.
                return (0, 0)
            # Longe de abrigos, deixa o recurso excedente para procurar o tipo
            # que falta ou deslocar-se para o local de construção.
        if isinstance(current_cell.structure, Storage):
            storage = current_cell.structure
            has_materials = any(self.inventory.quantity_of(kind) > 0 for kind in MaterialKind)
            has_surplus_food = self.inventory.food_quantity > 1.0 + 1e-9
            needs_food_from_storage = (
                self.hunger >= 35.0 and self.inventory.food_quantity < 1.0
                and storage.food_quantity > 0 and self.inventory.available_weight > 0
            )
            if has_materials or has_surplus_food or needs_food_from_storage:
                return (0, 0)

        # O agente chegou ao destino.
        if self.target == current_position:
            self._clear_target()

        # Sede alta invalida um alvo de comida para permitir procurar água.
        if self.thirst >= 40.0 and self.target is not None:
            target_cell = world.get_cell(*self.target)
            if not isinstance(target_cell.resource, Water):
                self._clear_target()

        # Escolhe um alvo e calcula uma rota quando necessário.
        if self.target is None or not self.path:
            self._select_target(
                nearby_cells,
                world,
                pathfinder,
            )

        if self.building_intent and self.target == current_position:
            return (0, 0)

        # Descarta a posição atual do início da rota.
        if self.path and self.path[0] == current_position:
            self.path.pop(0)

        # Executa o próximo movimento da rota.
        if self.path:
            next_x, next_y = self.path[0]

            return (
                next_x - self.x,
                next_y - self.y,
            )

        return self._choose_exploration_action(world)
    
    def _record_position(self) -> None:
        position = (self.x, self.y)
        self.visit_counts[position] = self.visit_counts.get(position, 0) + 1


    def _choose_exploration_action(self, world: World) -> Position:
        possible_actions = [
            (0, -1),
            (0, 1),
            (-1, 0),
            (1, 0),
        ]

        candidates = []

        for dx, dy in possible_actions:
            next_position = (self.x + dx, self.y + dy)

            if not world.is_walkable(*next_position):
                continue

            score = self._exploration_score(next_position)
            candidates.append(((dx, dy), score))

        if not candidates:
            return (0, 0)

        # Menor pontuação significa uma região menos explorada.
        min_score = min(score for _, score in candidates)

        least_explored = [
            action
            for action, score in candidates
            if score == min_score
        ]

        return self.rng.choice(least_explored)

    def _exploration_score(
        self,
        position: Position,
        radius: int = 2,
    ) -> float:
        center_x, center_y = position
        score = 0.0

        for (x, y), visits in self.visit_counts.items():
            distance = abs(x - center_x) + abs(y - center_y)

            if distance <= radius:
                # Visitas próximas pesam mais do que visitas distantes.
                score += visits / (distance + 1)

        return score
