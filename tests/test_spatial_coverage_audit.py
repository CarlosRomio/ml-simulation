from run_ecosystem_audit import _spatial_coverage_summary


def test_spatial_coverage_reports_unique_cells_and_revisits_per_individual():
    records = [
        {"individual_type": "CARNIVORE", "individual_id": "C001", "step": 1,
         "x": 1, "y": 1, "distance": 0, "activity": "WAITING", "behavior_intent": "EXPLORATION"},
        {"individual_type": "CARNIVORE", "individual_id": "C001", "step": 2,
         "x": 2, "y": 1, "distance": 1, "activity": "WALKING", "behavior_intent": "EXPLORATION"},
        {"individual_type": "CARNIVORE", "individual_id": "C001", "step": 3,
         "x": 1, "y": 1, "distance": 1, "activity": "WALKING", "behavior_intent": "EXPLORATION"},
        {"individual_type": "HERBIVORE", "individual_id": "V001", "step": 1,
         "x": 5, "y": 5, "distance": 0, "activity": "RESTING", "behavior_intent": "SEEK_FOOD"},
    ]

    rows = _spatial_coverage_summary(1, 7200, records, width=10, height=10)
    carnivore = next(row for row in rows if row["individual_type"] == "CARNIVORE")

    assert carnivore["unique_cells_visited"] == 2
    assert carnivore["world_cells"] == 100
    assert carnivore["world_coverage_ratio"] == 0.02
    assert carnivore["repeat_visit_observations"] == 1
    assert carnivore["repeat_visit_ratio"] == 1 / 3
    assert carnivore["total_distance"] == 2.0
