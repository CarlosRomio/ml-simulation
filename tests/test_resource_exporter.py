
import csv

import pytest

from metrics.resource_exporter import ResourceExporter


def test_export_csv_writes_header_and_rows(tmp_path):
    resource_history = [
        {
            "step": 0,
            "seeds": 0,
            "growing": 0,
            "mature": 2,
            "total": 2,
        },
        {
            "step": 1,
            "seeds": 1,
            "growing": 0,
            "mature": 2,
            "total": 3,
        },
    ]
    seeds_spawned_history = [0, 1]

    output_path = tmp_path / "resource_history.csv"

    result = ResourceExporter.export_csv(
        resource_history,
        seeds_spawned_history,
        output_path,
    )

    assert result == output_path
    assert output_path.exists()

    with output_path.open(
        "r",
        newline="",
        encoding="utf-8-sig",
    ) as csv_file:
        rows = list(csv.DictReader(csv_file))

    assert len(rows) == 2
    assert rows[0] == {
        "step": "0",
        "seeds": "0",
        "growing": "0",
        "mature": "2",
        "total": "2",
        "seeds_spawned": "0",
    }
    assert rows[1]["step"] == "1"
    assert rows[1]["seeds_spawned"] == "1"


def test_export_csv_creates_parent_directory(tmp_path):
    output_path = tmp_path / "results" / "ecology.csv"

    ResourceExporter.export_csv(
        [
            {
                "step": 0,
                "seeds": 0,
                "growing": 0,
                "mature": 0,
                "total": 0,
            }
        ],
        [0],
        output_path,
    )

    assert output_path.exists()


def test_export_csv_rejects_different_history_lengths(tmp_path):
    with pytest.raises(ValueError, match="mesmo tamanho"):
        ResourceExporter.export_csv(
            [
                {
                    "step": 0,
                    "seeds": 0,
                    "growing": 0,
                    "mature": 1,
                    "total": 1,
                }
            ],
            [],
            tmp_path / "invalid.csv",
        )


def test_export_csv_supports_empty_histories(tmp_path):
    output_path = tmp_path / "empty.csv"

    ResourceExporter.export_csv([], [], output_path)

    with output_path.open(
        "r",
        newline="",
        encoding="utf-8-sig",
    ) as csv_file:
        rows = list(csv.reader(csv_file))

    assert rows == [ResourceExporter.FIELDNAMES]
