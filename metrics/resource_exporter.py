
import csv
from pathlib import Path


class ResourceExporter:
    """Exporta o histórico ecológico da simulação para CSV."""

    FIELDNAMES = [
        "step",
        "seeds",
        "growing",
        "mature",
        "total",
        "seeds_spawned",
    ]

    @staticmethod
    def export_csv(
        resource_history: list[dict[str, int]],
        seeds_spawned_history: list[int],
        output_path: str | Path = "resource_history.csv",
    ) -> Path:
        """Exporta as métricas ecológicas e retorna o caminho do arquivo."""

        if len(resource_history) != len(seeds_spawned_history):
            raise ValueError(
                "Os históricos de recursos e de sementes geradas "
                "devem ter o mesmo tamanho."
            )

        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)

        with path.open("w", newline="", encoding="utf-8-sig") as csv_file:
            writer = csv.DictWriter(
                csv_file,
                fieldnames=ResourceExporter.FIELDNAMES,
                extrasaction="raise",
            )

            writer.writeheader()

            for resource_data, seeds_spawned in zip(
                resource_history,
                seeds_spawned_history,
            ):
                row = {
                    **resource_data,
                    "seeds_spawned": seeds_spawned,
                }

                writer.writerow(row)

        return path
