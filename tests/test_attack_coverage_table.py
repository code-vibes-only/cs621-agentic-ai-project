"""docs/attack-coverage.md must name only scenarios and tests that exist, and must be the current output of the generator."""
import re

from scheduler.config import ROOT, load_settings
from scheduler.contracts.scenario import load_split
from scheduler.eval import attack_coverage as coverage

SETTINGS = load_settings()
ALL = {s.id: s for split in ("dev", "heldout") for s in load_split(SETTINGS.data_dir, split)}


def defined_tests() -> set[str]:
    return {name for path in (ROOT / "tests").glob("test_*.py") for name in re.findall(r"^def (test_\w+)", path.read_text(encoding="utf-8"), re.M)}


def test_every_scenario_and_test_in_the_table_exists():
    tests = defined_tests()
    for row in coverage.COVERAGE:
        assert set(row["scenarios"]) <= set(ALL), row["case"]
        assert all(ALL[sid].ground_truth.attack for sid in row["scenarios"]), f"{row['case']}: a scenario named here is not an attack case"
        assert set(row["tests"]) <= tests, f"{row['case']}: {sorted(set(row['tests']) - tests)}"


def test_every_attack_scenario_is_in_the_table():
    named = {sid for row in coverage.COVERAGE for sid in row["scenarios"]}
    assert {i for i, s in ALL.items() if s.ground_truth.attack} <= named, "an attack scenario is in no row of the table"


def test_the_doc_is_current():
    assert coverage.DOC.read_text(encoding="utf-8").replace("\r\n", "\n") == coverage.markdown()
