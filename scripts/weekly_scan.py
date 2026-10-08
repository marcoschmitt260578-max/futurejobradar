"""Weekly scan for the Future Job Radar.

Asks Claude (with web search) to read the week's signals and science fiction,
invent 3-5 new future jobs and move existing ones on real evidence.
Merges the result into docs/jobs.json and writes a German report to reports/.

Env: ANTHROPIC_API_KEY (required), SCAN_MODEL (default claude-sonnet-5-5)
"""
import datetime, json, os, re, sys
from pathlib import Path
import anthropic

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "docs" / "jobs.json"
REPORTS = ROOT / "reports"
MODEL = os.environ.get("SCAN_MODEL") or "claude-sonnet-5-5"
SECTORS = ["ai", "finance", "robotics", "mobility", "built", "energy", "food", "space", "health", "care", "events"]
DRIVERS = ["ai", "robotics", "autonomy", "bio", "space", "energy", "quantum", "chain"]
SIGNAL_TYPES = {"analyst", "economist", "futurist", "scientist", "engineer", "strategist", "entrepreneur", "technologist", "market"}

SYSTEM = """You run the weekly scan for the "Future Job Radar" (futurejobradar.com), a public, English-language magazine that shows jobs technology could create in the next 2 to 10 years.

THESIS: Technology is a net job creator. In 1995 nobody was an Uber driver, Airbnb host or influencer. The tone is optimistic and curious, never doom.
METHOD: Facts + Fiction + Creative thinking = a job that could exist. Take real signals, combine them with science fiction, and invent the second-order jobs that follow ("if every car drives itself, what changes on motorways?", "if AI agents pay each other instantly over blockchains for almost nothing, who is needed?").

YOUR JOB THIS WEEK
1. Use web search to research roughly the last 7 days. Cover scientists, engineers, economists, strategists, futurists, entrepreneurs and analysts. Priority voices: Peter Diamandis / Moonshots, Cathie Wood / ARK Invest, Elon Musk (Optimus, SpaceX, robotaxi), Jensen Huang, Sam Altman, Dario Amodei, Ray Kurzweil, Amy Webb, WEF, McKinsey, PwC, BCG; plus market data (robot deployments and prices, robotaxi rides, launches, biotech approvals, fusion, energy, stablecoins, tokenized assets, agent payments, farm robots). Domains: AI & agents, finance, robotics, mobility, built world, energy & climate, food & farming, space, health & bio, care, events & exhibitions (live events, trade fairs, conferences, concerts, festivals, incentives), education.
2. Science fiction is a core source. Pick 1-2 "focus universes" this week, preferring titles used little or not at all so far (list given below). Star Trek (incl. Starfleet Academy, 2026) is a key universe; others: The Expanse, Star Wars, Dune, Foundation, Blade Runner, Black Mirror, Her, Westworld, Altered Carbon, Interstellar, The Martian, Minority Report, Ghost in the Shell, Severance, Murderbot, Andor, Silo, Three-Body Problem, Asimov, Kim Stanley Robinson, Neal Stephenson, William Gibson, Iain M. Banks, Becky Chambers, Cory Doctorow, Daniel Suarez. Ask: who works in that world and what do they do all day?
3. Invent 3 to 5 NEW jobs: creative, plausible within 2-10 years, not duplicates of existing ones, surprising second-order jobs rather than obvious ones. Each needs at least 2 real, sourced signals and at least 1 sci-fi reference. Favour sectors with fewer jobs.
4. Move existing jobs only on clear new evidence, by at most 1 year (horizon stays 2-10). Zero moves is fine.

LENGTH: Keep the final JSON compact: each claim max 30 words, 2-3 signals per job, linkedin_posts max 900 characters each, report_de max 150 words. Do not write long prose before the JSON.

RULES: Never invent quotes or attribute claims to people who did not make them. Paraphrase accurately in one sentence and include the URL you actually found. Never put your own extrapolation into a signal's claim. Do not reproduce copyrighted text. Plain English, no emojis.

OUTPUT: After researching, reply with ONE JSON object inside <result></result> tags and nothing after it:
{
 "focus": "focus universe(s)",
 "headline": "one punchy line for the scan log",
 "summary": "2 sentences: the week's signals and the focus universe",
 "cover": "id of the strongest new job (becomes 'Job of the week')",
 "new_jobs": [{
   "id": "kebab-case-unique", "title": "Job Title", "sector": one of SECTORS,
   "horizon": integer 2-10 = years after 2026 (the radar's fixed base year) until the job exists at scale,
   "drivers": {"ai":0-1,"robotics":0-1,"autonomy":0-1,"bio":0-1,"space":0-1,"energy":0-1,"quantum":0-1,"chain":0-1},
   "trigger": "When X happens, Y.", "what": "1-2 sentences", "day": "one concrete sentence: a day on the job",
   "skills": ["3 short skills"],
   "signals": [{"type": one of SIGNAL_TYPES, "who": "Person or org · source", "claim": "accurate paraphrase", "url": "https://..."}],
   "scifi": [{"title": "...", "year": 2014, "kind": "film|series|book", "echo": "one sentence"}],
   "professions": ["ids of existing professions this job grows out of"]
 }],
 "moves": [{"id": "existing id", "to": new_horizon, "signal": {"type": "...", "who": "...", "claim": "...", "url": "..."}}],
 "linkedin_hook": "one opening line for this week's LinkedIn post",
 "linkedin_posts": ["three ready-to-post English LinkedIn drafts in Marco's voice (optimistic, curious, plain words, no emojis, 3-5 hashtags, link goes in the first comment so not in the text): 1) Monday 'Job of the Week' about the cover job, ending with 'Would you take this job?'; 2) Wednesday 'What does your job become?' picking one of the professions; 3) a free format, e.g. 'Sci-fi saw it first' or 'moved inward'"],
 "report_de": "short report in German for Marco: focus universe, new jobs with one line each, moves with reason"
}"""


def compact_state(data):
    jobs = data["jobs"]
    used = {}
    for j in jobs:
        for f in j.get("scifi", []):
            used[f["title"]] = used.get(f["title"], 0) + 1
    counts = {s: sum(1 for j in jobs if j["sector"] == s) for s in SECTORS}
    return {
        "today": datetime.date.today().isoformat(),
        "sector_counts": counts,
        "existing_jobs": [{"id": j["id"], "title": j["title"], "sector": j["sector"], "horizon": j["horizon"]} for j in jobs],
        "scifi_titles_used": dict(sorted(used.items(), key=lambda x: -x[1])),
        "professions": [{"id": p["id"], "label": p["label"]} for p in data["meta"].get("professions", [])],
        "SECTORS": SECTORS, "SIGNAL_TYPES": sorted(SIGNAL_TYPES),
    }


def run_claude(state):
    client = anthropic.Anthropic()
    messages = [{"role": "user", "content": "Current radar state:\n" + json.dumps(state, ensure_ascii=False) + "\n\nRun this week's scan now."}]
    tools = [{"type": "web_search_20250305", "name": "web_search", "max_uses": 20}]
    text = ""
    for _ in range(8):  # continue while the server pauses long tool turns
        resp = client.messages.create(model=MODEL, max_tokens=20000, system=SYSTEM, tools=tools, messages=messages)
        text += "".join(b.text for b in resp.content if b.type == "text")
        print("stop_reason:", resp.stop_reason, "| output tokens:", resp.usage.output_tokens)
        if resp.stop_reason != "pause_turn":
            break
        messages.append({"role": "assistant", "content": resp.content})
    return parse_result(text)


def parse_result(text):
    """Pull the JSON out of <result>…</result>; tolerate a missing closing tag and inline citation markup."""
    text = re.sub(r"</?cite[^>]*>", "", text)
    i = text.rfind("<result>")
    if i < 0:
        raise SystemExit("No <result> in model output:\n" + text[-3000:])
    body = text[i + len("<result>"):].split("</result>")[0].strip()
    start = body.find("{")
    end = body.rfind("}")
    while end > start >= 0:
        try:
            return json.loads(body[start:end + 1])
        except json.JSONDecodeError:
            end = body.rfind("}", start, end)
    raise SystemExit("Could not parse <result> JSON (output probably cut off):\n" + body[-3000:])


def valid_signal(s):
    return isinstance(s, dict) and s.get("type") in SIGNAL_TYPES and s.get("who") and s.get("claim")


def clean_job(j, existing_ids, today):
    if not isinstance(j, dict) or not re.fullmatch(r"[a-z0-9]+(-[a-z0-9]+)*", str(j.get("id", ""))):
        return None, "bad id"
    if j["id"] in existing_ids:
        return None, "duplicate id"
    if j.get("sector") not in SECTORS:
        return None, "bad sector"
    try:
        h = int(j.get("horizon"))
    except Exception:
        return None, "bad horizon"
    h = max(2, min(10, h))
    sig = [s for s in j.get("signals", []) if valid_signal(s)]
    fic = [f for f in j.get("scifi", []) if isinstance(f, dict) and f.get("title") and f.get("echo")]
    if len(sig) < 2 or len(fic) < 1:
        return None, "needs 2 signals and 1 sci-fi"
    for k in ("title", "trigger", "what", "day"):
        if not str(j.get(k, "")).strip():
            return None, "missing " + k
    drivers = {k: float(j.get("drivers", {}).get(k, 0) or 0) for k in DRIVERS}
    if sum(drivers.values()) <= 0:
        drivers["ai"] = 1.0
    return {
        "id": j["id"], "title": j["title"].strip(), "sector": j["sector"], "horizon": h, "drivers": drivers,
        "trigger": j["trigger"].strip(), "what": j["what"].strip(), "day": j["day"].strip(),
        "skills": [str(x) for x in j.get("skills", [])][:3],
        "signals": [{k: s[k] for k in ("type", "who", "claim", "url") if s.get(k)} for s in sig],
        "scifi": [{"title": f["title"], "year": int(f.get("year") or 0), "kind": f.get("kind", "film"), "echo": f["echo"]} for f in fic],
        "added": today, "status": "new", "history": [{"date": today, "horizon": h}],
    }, None


def main():
    if not os.environ.get("ANTHROPIC_API_KEY"):
        sys.exit("ANTHROPIC_API_KEY is not set")
    data = json.loads(DATA.read_text())
    today = datetime.date.today().isoformat()
    result = run_claude(compact_state(data))

    for j in data["jobs"]:
        j["status"] = "stable"
    ids = {j["id"] for j in data["jobs"]}
    added, skipped = [], []
    for raw in result.get("new_jobs", [])[:5]:
        job, why = clean_job(raw, ids, today)
        if not job:
            skipped.append(f"{raw.get('id', '?')}: {why}")
            continue
        data["jobs"].append(job)
        ids.add(job["id"])
        added.append(job)
        for pid in raw.get("professions", []) or []:
            for p in data["meta"].get("professions", []):
                if p["id"] == pid and job["id"] not in p["jobs"]:
                    p["jobs"].append(job["id"])

    moved = []
    byid = {j["id"]: j for j in data["jobs"]}
    for mv in result.get("moves", []) or []:
        j = byid.get(mv.get("id"))
        if not j or j in added or not valid_signal(mv.get("signal")):
            continue
        try:
            to = int(mv["to"])
        except Exception:
            continue
        to = max(2, min(10, max(j["horizon"] - 1, min(j["horizon"] + 1, to))))
        if to == j["horizon"]:
            continue
        moved.append({"id": j["id"], "from": j["horizon"], "to": to})
        j["horizon"] = to
        j.setdefault("history", []).append({"date": today, "horizon": to})
        j["signals"].append({k: mv["signal"][k] for k in ("type", "who", "claim", "url") if mv["signal"].get(k)})

    if not added and not moved:
        sys.exit("Scan produced no valid changes; leaving data untouched. Skipped: " + "; ".join(skipped))

    meta = data["meta"]
    meta["scanNumber"] = int(meta.get("scanNumber", 0)) + 1
    meta["lastScan"] = today
    cover = result.get("cover")
    meta["cover"] = cover if cover in {a["id"] for a in added} else (added[0]["id"] if added else meta.get("cover"))
    data["scans"].append({
        "number": meta["scanNumber"], "date": today,
        "headline": str(result.get("headline", "Weekly scan")).strip(),
        "summary": str(result.get("summary", "")).strip(),
        "focus": result.get("focus", ""),
        "newJobs": [a["id"] for a in added], "moved": moved,
    })
    DATA.write_text(json.dumps(data, indent=1, ensure_ascii=False) + "\n")

    REPORTS.mkdir(exist_ok=True)
    report = [f"# Scan #{meta['scanNumber']} · {today}", "", f"**Focus:** {result.get('focus', '')}", "",
              result.get("report_de", ""), "", "## LinkedIn-Hook", "", result.get("linkedin_hook", ""), "",
              "## Post-Entwürfe", ""] + [f"### Entwurf {i + 1}\n\n{p}\n" for i, p in enumerate(result.get("linkedin_posts", []) or [])] + ["",
              "## Neue Jobs", ""] + [f"- **{a['title']}** (~{2026 + a['horizon']}): {a['trigger']}  \n  https://futurejobradar.com/jobs/{a['id']}/" for a in added]
    if moved:
        report += ["", "## Verschoben", ""] + [f"- {m['id']}: {m['from']} → {m['to']} Jahre" for m in moved]
    if skipped:
        report += ["", "## Verworfen (Validierung)", ""] + [f"- {s}" for s in skipped]
    (REPORTS / f"scan-{meta['scanNumber']:03d}.md").write_text("\n".join(report) + "\n")
    print(f"Scan #{meta['scanNumber']}: +{len(added)} jobs, {len(moved)} moved, {len(skipped)} skipped")


if __name__ == "__main__":
    main()
