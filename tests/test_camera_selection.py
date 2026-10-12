from visualization.camera import Camera


def test_screen_to_world_maps_cell_center_correctly():
    camera = Camera(world_width=20, world_height=20, view_width=10, view_height=10)
    camera.configure_viewport(300, 300, 30)
    camera.x = 2.0
    camera.y = 3.0
    assert camera.screen_to_world(10 + 2 * 30 + 15, 20 + 1 * 30 + 15, 10, 20) == (4, 4)


def test_screen_to_world_clamps_to_world_bounds():
    camera = Camera(world_width=10, world_height=10, view_width=10, view_height=10)
    camera.configure_viewport(300, 300, 30)
    assert camera.screen_to_world(-100, -100, 0, 0) == (0, 0)
    assert camera.screen_to_world(1000, 1000, 0, 0) == (9, 9)
