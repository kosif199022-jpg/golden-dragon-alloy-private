"""Compose existing recipe steps and their acceptance checks into one shared plan."""
import argparse
import json
from pathlib import Path


def compose(recipes, selected):
    by_id = {item["id"]: item for item in recipes}
    if len(by_id) != len(recipes):
        raise ValueError("Duplicate recipe ID")
    missing = set(selected) - by_id.keys()
    if missing:
        raise ValueError("Unknown recipe: " + ", ".join(sorted(missing)))
    steps = {}
    for name in dict.fromkeys(selected):
        for entry in by_id[name]["steps"]:
            key = (entry["action"].strip(), entry["accept"].strip())
            if not all(key):
                raise ValueError("Empty step or check in " + name)
            if key not in steps:
                steps[key] = {"action": key[0], "accept": key[1], "recipes": []}
            if name not in steps[key]["recipes"]:
                steps[key]["recipes"].append(name)
    return {"type": "plan", "recipes": list(dict.fromkeys(selected)), "steps": list(steps.values())}


if __name__ == "__main__":
    catalog = Path(__file__).resolve().parent.parent / "references" / "recipes.json"
    recipes = json.loads(catalog.read_text(encoding="utf-8"))
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("recipes", nargs="*", choices=None)
    args = parser.parse_args()
    result = compose(recipes, args.recipes) if args.recipes else [
        {"id": item["id"], "title": item["title"]} for item in recipes]
    print(json.dumps(result, ensure_ascii=False))
