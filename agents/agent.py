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
from agents.cognition import ActionCandidate, DecisionEngine, ExperienceMemory, Personality


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
        sociability: float | None = None,
        agent_id: str | None = None,
        personality: Personality | None = None,
    ):
        if vision_radius < 0:
            raise ValueError("vision_radius não pode ser negativo")

        self.x = x
        self.y = y
        self.rng = rng if rng is not None else random
        # Identificador legível, atribuído pela simulação se não for fornecido.
        self.agent_id = agent_id
        self.species = Species(species)
        self.hunt_target: Position | None = None
        self.running = False
        self.last_activity = "WAITING"
        self.is_sleeping = False
        self._sleep_selected = False
        self.sleep_started_step: int | None = None
        self.last_sleep_interruption_reason = ""
        self._sleep_interruption_event = ""

        self.target: Position | None = None
        self.path: list[Position] = []
        # Intenção operacional do alvo atual, preservada mesmo se o recurso-alvo
        # for coletado por outro agente enquanto este humano se desloca.
        self.target_intent = "UNCLASSIFIED"
        self.last_behavior_intent = "UNCLASSIFIED"

        self.needs = needs if needs is not None else AgentNeeds(
            max_energy=max_energy,
            energy=max_energy,
        )
        self.alive = self.needs.alive

        self.vision_radius = vision_radius
        self.visit_counts: dict[Position, int] = {}

        self.inventory = inventory if inventory is not None else Inventory()
        if personality is None:
            # Chamadas diretas mantêm sociabilidade neutra por compatibilidade;
            # os demais traços são individualizados pelo RNG do agente.
            personality = Personality.randomized(
                self.rng, sociability=0.5 if sociability is None else sociability
            )
        elif sociability is not None and personality.sociability != sociability:
            # Compatibilidade com código antigo que passava sociabilidade separada.
            from dataclasses import replace
            personality = replace(personality, sociability=float(sociability))
        self.personality = personality
        # Alias de compatibilidade; decisões novas leem o perfil de personalidade.
        self.sociability = self.personality.sociability
        self.decision_engine = DecisionEngine()
        self.experience_memory = ExperienceMemory()
        self.last_decision_trace: dict[str, object] | None = None
        self.last_decision_action_id: str | None = None
        self._decision_outcome_recorded = False
        self._current_decision_reward_eligible = False
        self._rest_selected = False
        self._waiting_selected = False
        self._selected_movement: Position | None = None
        self._decision_tick = 0
        # Posições de humanos vivos dentro do alcance social percebido neste passo.
        self.social_neighbors: list[Position] = []
        # Afinidades persistentes por identificador de indivíduo (0..1).
        self.social_affinities: dict[str, float] = {}
        # Afinidades dos humanos visíveis neste passo, indexadas por posição.
        self.social_neighbor_affinities: dict[Position, float] = {}
        self.social_neighbor_ids: dict[Position, str] = {}
        # Últimas posições conhecidas de indivíduos vistos anteriormente.
        # A memória é atualizada pela Simulation e expira após um TTL configurável.
        self.social_known_contacts: dict[str, dict[str, object]] = {}
        self.social_candidate_contacts: list[dict[str, object]] = []
        self.social_reunion_affinity_threshold = 0.2
        self.social_reunion_max_distance = 12
        self.last_social_decision: dict[str, object] = {
            "decision": "NOT_EVALUATED", "reason": "SOCIAL_DRIVE_NOT_REACHED"
        }
        # Estado de intenção usado pela política autônoma e resolvido pela simulação.
        self.building_intent = False
        self.occupied_positions: set[Position] = set()
        # Motivo do último movimento bloqueado, consumido pela instrumentação.
        self.last_movement_block_reason = ""
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
    def fatigue(self) -> float:
        return self.needs.fatigue

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
        self.target_intent = "UNCLASSIFIED"

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
                self.target_intent = "HUNT"
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
                self.target_intent = "BUILD_SHELTER"
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
                    self.target_intent = "SEEK_SHELTER"
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
                        self.target_intent = "GATHER_MATERIAL"
                        return

        # Sociabilidade é uma preferência de baixa prioridade. Memória de
        # indivíduos conhecidos permite tentar reencontros, sem teletransporte:
        # o agente navega até a última posição conhecida e atualiza a memória
        # apenas quando volta a perceber a pessoa.
        self.last_social_decision = {
            "decision": "OTHER_BEHAVIOR_PRIORITY",
            "reason": "SOCIAL_DRIVE_NOT_REACHED",
            "target_agent_id": "",
            "target_affinity": 0.0,
            "target_last_seen_age": -1,
            "target_x": "",
            "target_y": "",
        }
        if (
            self.sociability >= 0.35
            and self.hunger < 25.0
            and self.thirst < 25.0
            and self.energy > 25.0
        ):
            contacts: list[dict[str, object]] = list(self.social_candidate_contacts)
            # Compatibilidade com chamadas diretas de choose_action usadas por
            # testes e ferramentas que só fornecem a lista de vizinhos visíveis.
            if not contacts:
                for position in self.social_neighbors:
                    contacts.append({
                        "agent_id": self.social_neighbor_ids.get(position, ""),
                        "x": position[0], "y": position[1],
                        "affinity": self.social_neighbor_affinities.get(position, 0.0),
                        "last_seen_age": 0, "visible": True,
                    })

            eligible = [
                contact for contact in contacts
                if abs(int(contact["x"]) - self.x) + abs(int(contact["y"]) - self.y)
                <= self.social_reunion_max_distance
            ]
            if eligible:
                # Vínculos acima do limiar têm prioridade sobre estranhos mais
                # próximos. Sem vínculo relevante, mantém-se a aproximação
                # social geral já existente.
                familiar = [
                    contact for contact in eligible
                    if float(contact.get("affinity", 0.0)) >= self.social_reunion_affinity_threshold
                ]
                pool = familiar if familiar else [c for c in eligible if bool(c.get("visible", False))]
                if pool:
                    social_candidates: list[ActionCandidate] = []
                    for contact in pool:
                        contact_position = (int(contact["x"]), int(contact["y"]))
                        contact_distance = abs(contact_position[0] - self.x) + abs(contact_position[1] - self.y)
                        contact_affinity = float(contact.get("affinity", 0.0))
                        social_candidates.append(ActionCandidate(
                            action_id="SOCIAL_REUNION" if not bool(contact.get("visible", False)) else "SOCIAL_APPROACH",
                            intent="SOCIAL_REUNION" if not bool(contact.get("visible", False)) else "SOCIAL_APPROACH",
                            expected_benefit=contact_affinity,
                            opportunity=max(0.0, 1.0 - contact_distance / max(1, self.social_reunion_max_distance)),
                            cost=min(1.0, contact_distance / max(1, self.social_reunion_max_distance)) * 0.2,
                            social_value=1.0,
                            continues_current_goal=(self.target_intent == ("SOCIAL_REUNION" if not bool(contact.get("visible", False)) else "SOCIAL_APPROACH")),
                            target=contact_position,
                            metadata={"contact": contact},
                        ))
                    evaluated_social = self.decision_engine.evaluate_all(
                        social_candidates, self.personality, self.experience_memory, self.last_decision_action_id
                    )
                    chosen_evaluation = self.decision_engine.choose(
                        social_candidates, self.personality, self.rng, self.experience_memory, self.last_decision_action_id
                    )
                    if chosen_evaluation is None:
                        raise RuntimeError("A seleção social recebeu candidatos, mas não escolheu uma ação.")
                    chosen = chosen_evaluation.candidate.metadata["contact"]
                    self.last_decision_trace = self.decision_engine.trace(chosen_evaluation, evaluated_social)
                    self.last_decision_action_id = chosen_evaluation.candidate.action_id
                    self._current_decision_reward_eligible = True
                    self._decision_outcome_recorded = False
                    target_id = str(chosen.get("agent_id", ""))
                    target_position = (int(chosen["x"]), int(chosen["y"]))
                    affinity = float(chosen.get("affinity", 0.0))
                    last_seen_age = int(chosen.get("last_seen_age", 0))
                    visible = bool(chosen.get("visible", False))
                    neighbor_distance = abs(target_position[0] - self.x) + abs(target_position[1] - self.y)
                    preferred_distance = 1 if self.sociability >= 0.75 else (2 if self.sociability >= 0.5 else 3)
                    self.last_social_decision = {
                        "decision": "SOCIAL_ALREADY_CLOSE" if visible and neighbor_distance <= preferred_distance else "SOCIAL_REUNION" if not visible else "SOCIAL_APPROACH",
                        "reason": "KNOWN_AFFINITY" if affinity >= self.social_reunion_affinity_threshold else "GENERAL_SOCIAL_PREFERENCE",
                        "target_agent_id": target_id,
                        "target_affinity": round(affinity, 6),
                        "target_last_seen_age": last_seen_age,
                        "target_x": target_position[0],
                        "target_y": target_position[1],
                    }
                    if not visible and neighbor_distance <= preferred_distance:
                        # Chegou à última posição conhecida sem reencontrar o
                        # indivíduo: descarta apenas a memória espacial, não o vínculo.
                        self.social_known_contacts.pop(target_id, None)
                        self.last_social_decision["decision"] = "SOCIAL_REUNION_SEARCH_FAILED"
                        self.last_social_decision["reason"] = "LAST_KNOWN_POSITION_EMPTY"
                    elif neighbor_distance > preferred_distance:
                        candidates: list[Position] = []
                        for y in range(max(0, target_position[1] - preferred_distance), min(world.height, target_position[1] + preferred_distance + 1)):
                            for x in range(max(0, target_position[0] - preferred_distance), min(world.width, target_position[0] + preferred_distance + 1)):
                                candidate = (x, y)
                                if candidate == target_position or candidate == current_position:
                                    continue
                                if abs(x - target_position[0]) + abs(y - target_position[1]) != preferred_distance:
                                    continue
                                if candidate in self.occupied_positions:
                                    continue
                                cell = world.get_cell(x, y)
                                if cell.obstacle is not None or cell.resource is not None or cell.structure is not None:
                                    continue
                                candidates.append(candidate)
                        candidates.sort(key=lambda pos: (
                            abs(pos[0] - self.x) + abs(pos[1] - self.y), pos[1], pos[0]
                        ))
                        for candidate in candidates:
                            path = pathfinder(world, current_position, candidate)
                            if path is not None and len(path) > 1:
                                self.target = candidate
                                self.path = path
                                self.target_intent = "SOCIAL_REUNION" if not visible else "SOCIAL_APPROACH"
                                self.last_behavior_intent = self.target_intent
                                return
                        self.last_social_decision["decision"] = "SOCIAL_TARGET_UNREACHABLE"
                        self.last_social_decision["reason"] = "NO_PATH_TO_CONTACT"
                else:
                    self.last_social_decision = {
                        "decision": "NO_ELIGIBLE_CONTACT",
                        "reason": "NO_VISIBLE_OR_FAMILIAR_CONTACT_IN_RANGE",
                        "target_agent_id": "", "target_affinity": 0.0,
                        "target_last_seen_age": -1, "target_x": "", "target_y": "",
                    }
            else:
                self.last_social_decision = {
                    "decision": "NO_ELIGIBLE_CONTACT",
                    "reason": "NO_CONTACT_IN_REUNION_RANGE",
                    "target_agent_id": "", "target_affinity": 0.0,
                    "target_last_seen_age": -1, "target_x": "", "target_y": "",
                }
        elif self.social_neighbors or self.social_candidate_contacts:
            reason = "HUNGER_PRIORITY" if self.hunger >= 25.0 else "THIRST_PRIORITY" if self.thirst >= 25.0 else "ENERGY_PRIORITY" if self.energy <= 25.0 else "LOW_SOCIABILITY"
            self.last_social_decision = {
                "decision": "SOCIAL_SKIPPED_PRIORITY", "reason": reason,
                "target_agent_id": "", "target_affinity": 0.0,
                "target_last_seen_age": -1, "target_x": "", "target_y": "",
            }

        # As necessidades básicas e a exploração agora competem no mesmo
        # seletor cognitivo. A elegibilidade física continua explícita; o
        # seletor compara apenas ações que podem realmente ser executadas.
        self._select_needs_or_exploration_target(world, pathfinder, current_position)

    def _nearest_reachable_target(
        self,
        world: World,
        pathfinder: Pathfinder,
        current_position: Position,
        positions: list[Position],
    ) -> tuple[Position, list[Position]] | None:
        """Retorna o alvo alcançável mais próximo, usando distância Manhattan como pré-filtro."""
        ordered = sorted(
            set(positions),
            key=lambda position: (
                abs(position[0] - self.x) + abs(position[1] - self.y),
                position[1], position[0],
            ),
        )
        for position in ordered:
            if position == current_position:
                continue
            path = pathfinder(world, current_position, position)
            if path is not None and len(path) > 1:
                return position, path
        return None

    def _select_needs_or_exploration_target(
        self,
        world: World,
        pathfinder: Pathfinder,
        current_position: Position,
    ) -> None:
        """Compara busca de alimento/água, repouso e exploração em uma decisão."""
        candidates: list[ActionCandidate] = []
        distance_scale = max(6.0, float(self.vision_radius * 3))

        food_positions = [
            (cell.x, cell.y)
            for row in world.grid
            for cell in row
            if isinstance(cell.resource, (Plant, Food))
            and self.can_collect_resource(cell.resource)
            and (cell.x, cell.y) != current_position
        ]
        food_target = self._nearest_reachable_target(
            world, pathfinder, current_position, food_positions
        )
        if food_target is not None:
            target, path = food_target
            distance = max(0, len(path) - 1)
            hunger_need = self.hunger / max(1.0, self.needs.max_hunger)
            inventory_scarcity = 1.0 - min(1.0, self.inventory.food_quantity / 10.0)
            benefit = min(1.0, 0.30 + 0.50 * hunger_need + 0.20 * inventory_scarcity)
            proximity = max(0.0, 1.0 - distance / distance_scale)
            candidates.append(ActionCandidate(
                action_id="SEEK_FOOD",
                intent="SEEK_FOOD",
                expected_benefit=benefit,
                urgency=hunger_need,
                opportunity=proximity,
                cost=min(1.0, distance / distance_scale) * 0.30,
                risk=min(1.0, distance / distance_scale) * 0.25,
                continues_current_goal=self.target_intent == "SEEK_FOOD",
                target=target,
                metadata={"path": path, "distance": distance},
            ))

        # Água passa a ser uma alternativa preventiva a partir de uma sede
        # moderada, mas sua urgência cresce continuamente com a necessidade.
        thirst_need = self.thirst / max(1.0, self.needs.max_thirst)
        if self.thirst >= 12.0:
            water_target = self._nearest_reachable_target(
                world, pathfinder, current_position, world.get_water_positions()
            )
            if water_target is not None:
                target, path = water_target
                distance = max(0, len(path) - 1)
                proximity = max(0.0, 1.0 - distance / distance_scale)
                candidates.append(ActionCandidate(
                    action_id="SEEK_WATER",
                    intent="SEEK_WATER",
                    expected_benefit=min(1.0, 0.28 + 0.62 * thirst_need),
                    urgency=thirst_need,
                    opportunity=proximity,
                    cost=min(1.0, distance / distance_scale) * 0.30,
                    risk=min(1.0, distance / distance_scale) * 0.25,
                    continues_current_goal=self.target_intent == "SEEK_WATER",
                    target=target,
                    metadata={"path": path, "distance": distance},
                ))

        current_cell = world.get_cell(*current_position)
        in_shelter = isinstance(current_cell.structure, Shelter)
        energy_need = 1.0 - self.energy / max(1.0, self.max_energy)
        fatigue_need = self.needs.fatigue / max(1.0, self.needs.max_fatigue)
        rest_threshold = 70.0 if in_shelter else 55.0
        if (
            self.energy < rest_threshold
            and self.hunger < 35.0
            and self.thirst < 40.0
        ):
            candidates.append(ActionCandidate(
                action_id="REST",
                intent="REST_IN_SHELTER" if in_shelter else "REST",
                expected_benefit=min(1.0, 0.30 + 0.55 * energy_need + (0.15 if in_shelter else 0.0)),
                urgency=energy_need,
                opportunity=0.90 if in_shelter else 0.30,
                cost=0.0 if in_shelter else 0.10,
                continues_current_goal=self.last_behavior_intent in {"REST", "REST_IN_SHELTER"},
                target=current_position,
                metadata={"in_shelter": in_shelter},
            ))

        # Sono é uma ação persistente, distinta de descanso. Necessidades urgentes
        # impedem iniciar o sono; necessidades moderadas ainda podem ser atendidas
        # durante o sono quando há alimento no inventário.
        sleep_threshold = getattr(getattr(self, "physiology_config", None), "sleep_start_threshold", 65.0)
        can_sleep = (
            not getattr(self, "_sleep_blocked_this_step", False)
            and self.needs.fatigue >= sleep_threshold
            and self.thirst < 40.0
            and (self.hunger < 35.0 or self.inventory.food_quantity >= 1.0)
        )
        if can_sleep:
            candidates.append(ActionCandidate(
                action_id="SLEEP", intent="SLEEP",
                expected_benefit=min(1.0, 0.55 + 0.45 * fatigue_need),
                urgency=min(1.0, fatigue_need * 1.25),
                opportunity=0.85 if in_shelter else 0.45,
                cost=0.0 if in_shelter else 0.12,
                risk=0.05 if in_shelter else 0.25,
                continues_current_goal=self.last_behavior_intent == "SLEEP",
                target=current_position,
                metadata={"in_shelter": in_shelter},
            ))

        # Esperar é uma ação explícita: não desloca o agente e não equivale a
        # descansar. É útil quando nenhuma alternativa imediata compensa o custo.
        candidates.append(ActionCandidate(
            action_id="WAIT", intent="WAIT",
            expected_benefit=0.02 + 0.45 * fatigue_need,
            urgency=0.30 * fatigue_need,
            opportunity=0.05 + 0.30 * fatigue_need,
            cost=0.0, risk=0.0,
            continues_current_goal=self.last_behavior_intent == "WAIT",
            target=current_position,
        ))

        # Exploração é uma alternativa real, mas não deve automaticamente
        # superar uma necessidade importante só por haver uma célula inédita.
        possible_moves = ((0, -1), (0, 1), (-1, 0), (1, 0))
        for dx, dy in possible_moves:
            target = (self.x + dx, self.y + dy)
            if not world.is_walkable(*target):
                continue
            visit_score = self._exploration_score(target)
            novelty = 1.0 / (1.0 + visit_score)
            candidates.append(ActionCandidate(
                action_id="EXPLORE",
                intent="EXPLORATION",
                expected_benefit=0.15 + 0.25 * novelty,
                opportunity=0.50 * novelty,
                cost=min(1.0, 0.08 + 0.35 * fatigue_need),
                exploration_value=novelty,
                continues_current_goal=self.target_intent == "EXPLORATION",
                target=target,
                metadata={"movement": (dx, dy), "visit_score": visit_score},
            ))

        if not candidates:
            self._clear_target()
            return

        evaluated = self.decision_engine.evaluate_all(
            candidates, self.personality, self.experience_memory, self.last_decision_action_id
        )
        chosen = self.decision_engine.choose(
            candidates, self.personality, self.rng,
            self.experience_memory, self.last_decision_action_id,
        )
        if chosen is None:
            self._clear_target()
            return

        self.last_decision_trace = self.decision_engine.trace(chosen, evaluated)
        self.last_decision_action_id = chosen.candidate.action_id
        self._waiting_selected = False
        self._current_decision_reward_eligible = True
        self._decision_outcome_recorded = False
        action = chosen.candidate

        if action.action_id == "SLEEP":
            self._clear_target()
            self.target_intent = "SLEEP"
            self.last_behavior_intent = "SLEEP"
            self.is_sleeping = True
            self.last_sleep_interruption_reason = ""
            self._sleep_selected = True
            return

        if action.action_id == "WAIT":
            self._clear_target()
            self.target_intent = "WAIT"
            self.last_behavior_intent = "WAIT"
            self._waiting_selected = True
            return

        if action.action_id == "REST":
            self._clear_target()
            self.target_intent = "REST"
            self.last_behavior_intent = str(action.intent)
            self._rest_selected = True
            return

        self.target = action.target
        self.path = list(action.metadata.get("path", []))
        self._waiting_selected = False
        if action.action_id == "EXPLORE":
            # Exploração é uma ação direta de um passo, sem criar um alvo
            # persistente que possa ser confundido com uma rota para recurso.
            self._clear_target()
            self._waiting_selected = False
            self._selected_movement = action.metadata["movement"]
            self.last_behavior_intent = action.intent
            return
        self.target_intent = action.intent
        self.last_behavior_intent = action.intent

    def choose_action(
        self,
        nearby_cells: list[Cell],
        world: World,
        pathfinder: Pathfinder = find_path,
    ) -> Position:
        self._record_position()
        self._decision_tick += 1
        self._rest_selected = False
        self._sleep_selected = False
        self._waiting_selected = True
        self._selected_movement = None
        # Mantém a última decisão cognitiva visível para auditoria, mas só
        # permite atribuir recompensa se o seletor voltar a escolher neste passo.
        self._current_decision_reward_eligible = False
        # Reavalia planos fisiológicos periodicamente, evitando que um agente
        # persista em buscar comida enquanto a sede/energia se torna crítica.
        if (
            self.target is not None
            and self.target_intent in {"SEEK_FOOD", "SEEK_WATER"}
            and self._decision_tick % 5 == 0
        ):
            self._clear_target()
        if (
            self.needs.fatigue >= getattr(getattr(self, "physiology_config", None), "sleep_start_threshold", 65.0)
            and self.hunger < 50.0 and self.thirst < 50.0
            and self.target is not None and self.target_intent == "EXPLORATION"
        ):
            self._clear_target()
        self.last_social_decision = {
            "decision": "OTHER_BEHAVIOR_PRIORITY", "reason": "SOCIAL_DRIVE_NOT_REACHED",
            "target_agent_id": "", "target_affinity": 0.0,
            "target_last_seen_age": -1, "target_x": "", "target_y": "",
        }
        current_position = (self.x, self.y)
        # Na simulação multiagente, planeja evitando posições ocupadas no estado
        # atual. A ocupação muda a cada passo, então esta visão é recalculada
        # pelo chamador antes de cada decisão.
        dynamic_blocked_positions: set[Position] | None = None
        if pathfinder is find_path and self.occupied_positions:
            dynamic_blocked_positions = set(self.occupied_positions)
            dynamic_blocked_positions.discard(current_position)

            def pathfinder_avoiding_occupants(
                route_world: World, start: Position, goal: Position
            ) -> list[Position] | None:
                blocked_for_route = set(dynamic_blocked_positions or ())
                # Humanos precisam navegar até a posição de uma presa para
                # aproximar-se dela; o resolvedor de movimento impede ocupar a
                # célula enquanto a presa continua ali.
                if self.hunt_target is not None and goal == self.hunt_target:
                    blocked_for_route.discard(goal)
                return find_path(
                    route_world, start, goal,
                    blocked_positions=blocked_for_route,
                )

            pathfinder = pathfinder_avoiding_occupants

        # Se o próximo passo ficou ocupado desde o planejamento anterior,
        # recalcula a rota preservando o objetivo. Se o próprio destino estiver
        # ocupado/inacessível, libera-o para selecionar outro recurso alcançável.
        if self.target is not None and self.path and dynamic_blocked_positions is not None:
            next_step_index = 1 if self.path[0] == current_position else 0
            if (
                next_step_index < len(self.path)
                and self.path[next_step_index] in dynamic_blocked_positions
            ):
                refreshed_path = pathfinder(world, current_position, self.target)
                if refreshed_path is not None and len(refreshed_path) > 1:
                    self.path = refreshed_path
                else:
                    self._clear_target()
        current_cell = world.get_cell(*current_position)
        if self.thirst >= 1.0 and isinstance(current_cell.resource, Water):
            self.last_behavior_intent = "DRINK_WATER"
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
                self.last_behavior_intent = "COLLECT_MATERIAL"
                return (0, 0)
            if self._has_nearby_shelter(current_position, world):
                # Próximo de um abrigo, coleta de materiais é oportunista.
                self.last_behavior_intent = "COLLECT_MATERIAL"
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
                self.last_behavior_intent = "INTERACT_STORAGE"
                return (0, 0)

        # A fadiga elevada inicia sono persistente, desde que não haja uma
        # necessidade alimentar/hídrica que deva ser resolvida primeiro.
        physiology = getattr(self, "physiology_config", None)
        sleep_threshold = getattr(physiology, "sleep_start_threshold", 65.0)
        if (
            not getattr(self, "_sleep_blocked_this_step", False)
            and self.needs.fatigue >= sleep_threshold
            and self.thirst < 40.0
            and (self.hunger < 35.0 or self.inventory.food_quantity >= 1.0)
        ):
            self._clear_target()
            self.is_sleeping = True
            self.last_sleep_interruption_reason = ""
            self._sleep_selected = True
            self._waiting_selected = False
            self.target_intent = "SLEEP"
            self.last_behavior_intent = "SLEEP"
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
            if self._rest_selected:
                return (0, 0)
            if self.target_intent == "WAIT":
                return (0, 0)
            if self._selected_movement is not None:
                return self._selected_movement

        # Classifica a intenção operacional real pelo alvo selecionado, sem inferi-la
        # apenas a partir do fato de o agente ter se deslocado.
        if self.building_intent:
            self.last_behavior_intent = "BUILD_SHELTER"
        elif self.target is not None:
            self.last_behavior_intent = self.target_intent
            if self.last_behavior_intent == "UNCLASSIFIED":
                self.last_behavior_intent = "NAVIGATE_TARGET"
        else:
            self.last_behavior_intent = "EXPLORATION"

        if self.building_intent and self.target == current_position:
            return (0, 0)

        # Descarta a posição atual do início da rota.
        if self.path and self.path[0] == current_position:
            self.path.pop(0)

        # Executa o próximo movimento da rota.
        if self.path:
            next_x, next_y = self.path[0]
            self._waiting_selected = False

            return (
                next_x - self.x,
                next_y - self.y,
            )

        self.last_behavior_intent = "EXPLORATION"
        return self._choose_exploration_action(world)
    
    def record_action_outcome(self, reward: float) -> None:
        """Registra explicitamente o resultado da última ação cognitiva escolhida.

        O chamador deve fornecer uma recompensa normalizada entre -1 e 1.
        A simulação ainda não atribui recompensas automaticamente: primeiro
        precisamos definir como creditar resultados de ações de vários passos.
        """
        if self.last_decision_trace is None or not self._current_decision_reward_eligible:
            raise RuntimeError("Não há uma decisão cognitiva recém-selecionada para avaliar.")
        if self._decision_outcome_recorded:
            raise RuntimeError("O resultado desta decisão já foi registrado.")
        action_id = str(self.last_decision_trace["action_id"])
        self.experience_memory.observe(action_id, reward)
        self._decision_outcome_recorded = True

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

        candidates: list[ActionCandidate] = []

        for index, (dx, dy) in enumerate(possible_actions):
            next_position = (self.x + dx, self.y + dy)

            if not world.is_walkable(*next_position):
                continue

            visit_score = self._exploration_score(next_position)
            novelty = 1.0 / (1.0 + visit_score)
            candidates.append(ActionCandidate(
                action_id="EXPLORE",
                intent="EXPLORATION",
                expected_benefit=novelty,
                opportunity=novelty,
                cost=0.1,
                exploration_value=novelty,
                target=next_position,
                metadata={"movement": (dx, dy), "visit_score": visit_score},
            ))

        if not candidates:
            self.last_decision_trace = None
            self.last_decision_action_id = None
            return (0, 0)

        evaluated = self.decision_engine.evaluate_all(
            candidates, self.personality, self.experience_memory, self.last_decision_action_id
        )
        chosen = self.decision_engine.choose(
            candidates, self.personality, self.rng, self.experience_memory, self.last_decision_action_id
        )
        if chosen is None:
            return (0, 0)
        self.last_decision_trace = self.decision_engine.trace(chosen, evaluated)
        self.last_decision_action_id = chosen.candidate.action_id
        self._waiting_selected = False
        self._current_decision_reward_eligible = True
        self._decision_outcome_recorded = False
        return chosen.candidate.metadata["movement"]

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
