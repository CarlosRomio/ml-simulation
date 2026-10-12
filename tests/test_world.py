
from environment.world import World


world = World(width=10, height=10, food_count=10)

food_count = sum(
    1
    for row in world.grid
    for cell in row
    if cell.resource is not None
)

print(f"Tamanho: {world.width} x {world.height}")
print(f"Células: {world.width * world.height}")
print(f"Comidas: {food_count}")

assert len(world.grid) == 10
assert all(len(row) == 10 for row in world.grid)
assert food_count == 10

print("\nTodas as verificações passaram!")
