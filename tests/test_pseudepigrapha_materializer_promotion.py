from __future__ import annotations

from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "registry" / "materializers.yaml"
EXPECTED_REF = "317e960e05ca7f36f35a11fcf567285312951095"


def _entry() -> dict:
    document = yaml.safe_load(REGISTRY.read_text(encoding="utf-8"))
    return next(item for item in document["plugins"] if item["id"] == "pseudepigrapha-tf")


def test_pseudepigrapha_stable_registry_points_at_verified_v020_release():
    plugin = _entry()

    assert plugin["version"] == "0.2.0"
    assert plugin["ref"] == EXPECTED_REF
    assert len(plugin["ref"]) == 40
    assert plugin["repository"] == "alexsosn/Pseudepigrapha-TF"
    assert plugin["release_tracking"] == {
        "mode": "github-releases",
        "channel": "stable",
        "tag_prefix": "v",
    }
    assert plugin["materializers"] == ["ocp-text-fabric"]
