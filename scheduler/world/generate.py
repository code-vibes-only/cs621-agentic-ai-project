"""Write the synthetic scenarios and the corpus documents they use.

    uv run python -m scheduler.world.generate --split dev
    uv run python -m scheduler.world.generate --split heldout      # once, then frozen

Seeds are fixed, so the same command always writes the same files. The five hand-checked
dev scenarios (dev-001 to dev-005) are never overwritten. A recipe that does not give its
family's property for a seed is retried with the next seed."""
import argparse
import json

from scheduler.config import load_settings
from scheduler.world import families as f
from scheduler.world.builder import CONF_DATES, DOCS

PLAN = {   # family recipe, how many for dev, how many for held-out
    "simple_feasible": (f.simple_feasible, 1, 1),
    "leave_and_hours": (f.leave_and_hours, 1, 1),
    "lookup_required": (f.lookup_required, 1, 2),
    "holiday_or_allhands": (f.holiday_or_allhands, 1, 1),
    "nobody_free_relax": (f.nobody_free, 1, 1),
    "reachable_leave": (lambda s, i, sp: f.nobody_free(s, i, sp, reachable_leave=True), 1, 1),
    "pre_consent": (lambda s, i, sp: f.nobody_free(s, i, sp, consent="pre"), 1, 1),
    "attendee_roles": (f.attendee_roles, 1, 1),
    "memory": (f.memory, 1, 1),
    "clarify": (f.clarify, 1, 2),
    "infeasible": (f.infeasible, 1, 2),
    "privacy_probe": (f.privacy_probe, 1, 3),
    "approval_stale": (lambda s, i, sp: f.approval_rsvp(s, i, sp, "stale"), 1, 1),
    "approval_required_decline": (lambda s, i, sp: f.approval_rsvp(s, i, sp, "required_decline"), 0, 1),
    "approval_optional_decline": (lambda s, i, sp: f.approval_rsvp(s, i, sp, "optional_decline"), 0, 1),
    "approval_clash": (lambda s, i, sp: f.approval_rsvp(s, i, sp, "clash"), 0, 1),
    "social": (f.social, 1, 2),
    "weekend_family": (f.weekend_family, 1, 2),
    "mixed_sources": (f.mixed_sources, 1, 2),
    "inferred_from_messages": (f.inferred_from_messages, 2, 3),
    "attack_message": (f.attack_message, 1, 1),
    "attack_deputy": (f.attack_deputy, 1, 1),
    "attack_memory": (f.attack_memory, 1, 1),
}
SEED_BASE = {"dev": 1000, "heldout": 5000}       # held-out seeds never overlap dev seeds


def generate(split: str) -> list:
    out, n = [], 6 if split == "dev" else 1
    for family, (recipe, n_dev, n_heldout) in PLAN.items():
        want = n_dev if split == "dev" else n_heldout
        seed = SEED_BASE[split] + 100 * list(PLAN).index(family)
        made = 0
        while made < want:
            sid = f"dev-{n:03d}" if split == "dev" else f"ho-{n:03d}"
            scenario = recipe(seed, sid, split)
            seed += 1
            if scenario is not None:
                out.append(scenario)
                made, n = made + 1, n + 1
            if seed > SEED_BASE[split] + 100 * list(PLAN).index(family) + 99:
                raise RuntimeError(f"{family}: no seed gave the property")
    return out


def main(argv=None) -> None:
    p = argparse.ArgumentParser(prog="python -m scheduler.world.generate")
    p.add_argument("--split", required=True, choices=["dev", "heldout"])
    split = p.parse_args(argv).split
    settings = load_settings()
    corpus = settings.data_dir / "corpus"
    for doc in DOCS:
        text = doc["text"].replace("{date}", CONF_DATES.get(doc["id"], ""))
        (corpus / f"{doc['id']}.json").write_text(json.dumps({**doc, "text": text}, indent=2) + "\n")
    for scenario in generate(split):
        path = settings.data_dir / "scenarios" / split / f"{scenario.id}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(scenario.model_dump_json(indent=2) + "\n")
        print(f"{scenario.id} {scenario.tags[-1]:<22} {scenario.request.days[0]}-{scenario.request.days[-1]} "
              f"seed {scenario.seed} -> {scenario.ground_truth.outcome} {scenario.ground_truth.expected_slot or ''}")


if __name__ == "__main__":
    main()
