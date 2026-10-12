
from random import Random

from agents.agent import Agent
from environment.world import World
from metrics.resource_exporter import ResourceExporter
from simulation.simulation import Simulation


SEED = 42
STEPS = 500

world = World(
    width=30,
    height=30,
    food_count=18,
    obstacle_count=9,
    reserved_cells={(15, 15)},
    rng=Random(SEED),
)

agent = Agent(
    x=15,
    y=15,
    vision_radius=6,
)

simulation = Simulation(
    world=world,
    agent=agent,
    seed_spawn_count=1,
    max_plants=100,
    resource_update_interval=1,
)

simulation.run(STEPS)

output_path = ResourceExporter.export_csv(
    simulation.resource_history,
    simulation.seeds_spawned_history,
    "results/resource_history.csv",
)

counts = world.get_plant_counts()

print(simulation.metrics.report())

print("\n=== Estado final do ecossistema ===")
print(f"Passos executados: {simulation.steps}/{STEPS}")
print(f"Sementes geradas: {sum(simulation.seeds_spawned_history)}")
print(f"Sementes restantes: {counts['seeds']}")
print(f"Plantas em crescimento: {counts['growing']}")
print(f"Plantas maduras: {counts['mature']}")
print(f"Total de plantas: {counts['total']}")
print(f"Registros ecológicos: {len(simulation.resource_history)}")
print(f"CSV exportado: {output_path}")
