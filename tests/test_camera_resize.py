from visualization.camera import Camera


def test_camera_viewport_tracks_resized_window_area():
    camera = Camera(world_width=100, world_height=100, view_width=20, view_height=20)
    camera.configure_viewport(600, 450, 30)
    assert camera.visible_width == 20
    assert camera.visible_height == 15

    camera.configure_viewport(900, 600, 30)
    assert camera.visible_width == 30
    assert camera.visible_height == 20
    assert 0 <= camera.x <= camera.world_width - camera.visible_width
    assert 0 <= camera.y <= camera.world_height - camera.visible_height
