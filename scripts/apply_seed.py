"""One-off seeds: merge scripts/seed_*.json into docs/jobs.json (idempotent).

A seed adds hand-curated jobs (e.g. a new sector), can remove or move jobs,
set the cover story and log the change as its own entry in the scan log.
"""
import datetime, json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "docs" / "jobs.json"


def apply(seed, data, today):
    new = [j for j in seed.get("jobs", []) if j["id"] not in {x["id"] for x in data["jobs"]}]
    gone = set(seed.get("remove", []))
    moves = seed.get("move", {})
    if not new and not (gone & {j["id"] for j in data["jobs"]}) and all(
            j["sector"] == moves[j["id"]] for j in data["jobs"] if j["id"] in moves):
        return False
    data["jobs"] = [j for j in data["jobs"] if j["id"] not in gone]
    for p in data["meta"].get("professions", []):
        p["jobs"] = [x for x in p["jobs"] if x not in gone]
    for j in data["jobs"]:
        if j["id"] in moves:
            j["sector"] = moves[j["id"]]
    for j in new:
        profs = j.pop("professions", [])
        j.update({"added": today, "status": "new", "history": [{"date": today, "horizon": j["horizon"]}]})
        data["jobs"].append(j)
        for p in data["meta"].get("professions", []):
            if p["id"] in profs and j["id"] not in p["jobs"]:
                p["jobs"].append(j["id"])
    meta = data["meta"]
    if seed.get("cover"):
        meta["cover"] = seed["cover"]
    if new and seed.get("scan"):
        meta["scanNumber"] = int(meta.get("scanNumber", 0)) + 1
        meta["lastScan"] = today
        data["scans"].append({"number": meta["scanNumber"], "date": today, **seed["scan"],
                              "newJobs": [j["id"] for j in new], "moved": []})
    return True


def main():
    data = json.loads(DATA.read_text())
    today = datetime.date.today().isoformat()
    changed = False
    for f in sorted((ROOT / "scripts").glob("seed_*.json")):
        if apply(json.loads(f.read_text()), data, today):
            print("Applied", f.name)
            changed = True
    if changed:
        DATA.write_text(json.dumps(data, indent=1, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    main()
