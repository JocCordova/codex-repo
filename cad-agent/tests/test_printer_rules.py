from pathlib import Path

import yaml


def test_printer_preset_exists() -> None:
    root = Path(__file__).resolve().parents[1]
    data = yaml.safe_load((root / "specs" / "printers.yaml").read_text(encoding="utf-8"))
    p1s = data["printers"]["bambulab_p1s"]
    assert p1s["process"] == "FDM"
    assert p1s["build_volume_mm"]["x"] == 256
