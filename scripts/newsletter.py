"""Turn the latest scan into the weekly newsletter and hand it to Brevo.

Runs after weekly_scan.py. Does nothing unless BREVO_API_KEY and BREVO_LIST_ID are set.

Env:
  BREVO_API_KEY     Brevo API key (GitHub secret)
  BREVO_LIST_ID     id of the Brevo contact list (GitHub variable)
  NEWSLETTER_MODE   draft (default): campaign waits in Brevo until Marco presses send
                    schedule: sent automatically at NEWSLETTER_SEND_UTC (default 09:00 UTC) today
                    send: sent immediately
  SENDER_EMAIL      verified sender in Brevo (default: contact_email from site_config.json)
"""
import datetime, html, json, os, sys, urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "docs" / "jobs.json"
CONFIG = json.loads((ROOT / "scripts" / "site_config.json").read_text())
SITE = os.environ.get("SITE_URL", "https://futurejobradar.com").rstrip("/")
BASE_YEAR = 2026
e = html.escape


def brevo(path, payload, key):
    req = urllib.request.Request("https://api.brevo.com/v3" + path, data=json.dumps(payload).encode(), method="POST",
                                 headers={"api-key": key, "content-type": "application/json", "accept": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as r:
        body = r.read()
        return json.loads(body) if body else {}


def year(j):
    return BASE_YEAR + j["horizon"]


def build(data):
    scan = data["scans"][-1]
    byid = {j["id"]: j for j in data["jobs"]}
    new = [byid[i] for i in scan.get("newJobs", []) if i in byid]
    cover = byid.get(data["meta"].get("cover")) or (new[0] if new else None)
    others = [j for j in new if j is not cover]
    moved = [(byid[m["id"]], m) for m in scan.get("moved", []) if m["id"] in byid]

    def link(j):
        return f"{SITE}/jobs/{j['id']}/"

    gold, paper, ink, mute = "#f2c14e", "#f3eee3", "#0d1226", "#a9afc6"
    head = "font-family:'Arial Narrow',Arial,sans-serif;font-weight:900;text-transform:uppercase;letter-spacing:.01em;margin:0"
    body = "font-family:Georgia,'Times New Roman',serif;font-size:17px;line-height:1.55;color:" + paper
    mono = "font-family:Menlo,Consolas,monospace;font-size:11px;letter-spacing:.16em;text-transform:uppercase;color:" + gold

    parts = [f"""<p style="{mono};margin:0 0 6px">Future Job Radar · Issue {scan['number']} · {e(scan['date'])}</p>
<h1 style="{head};font-size:28px;line-height:1.05;color:{paper}">{e(scan.get('headline', 'This week on the radar'))}</h1>
<p style="{body};color:{mute};margin:14px 0 26px">{e(scan.get('summary', ''))}</p>"""]
    if cover:
        parts.append(f"""<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:{paper};margin:0 0 26px"><tr><td style="padding:22px">
<p style="{mono};color:#7a5a00;margin:0 0 8px">Job of the week · arrives ~{year(cover)}</p>
<h2 style="{head};font-size:30px;line-height:1;color:{ink}">{e(cover['title'])}</h2>
<p style="{body};color:#20263f;font-style:italic;margin:10px 0 8px">{e(cover['trigger'])}</p>
<p style="{body};color:#20263f;margin:0 0 8px">{e(cover['what'])}</p>
<p style="{body};color:#20263f;margin:0 0 14px"><b>A day on the job:</b> {e(cover['day'])}</p>
<a href="{link(cover)}" style="display:inline-block;background:{ink};color:{gold};{mono};padding:11px 16px;text-decoration:none">Read the full story →</a>
</td></tr></table>""")
    if others:
        parts.append(f'<p style="{mono};margin:0 0 10px">Also new this week</p>')
        for j in others:
            parts.append(f"""<p style="{body};margin:0 0 14px"><a href="{link(j)}" style="color:{paper};font-weight:bold;text-decoration:none;border-bottom:1px solid {gold}">{e(j['title'])}</a> <span style="color:{gold}">~{year(j)}</span><br><span style="color:{mute}">{e(j['trigger'])}</span></p>""")
    if moved:
        parts.append(f'<p style="{mono};margin:22px 0 10px">Moved on the radar</p>')
        for j, m in moved:
            arrow = "closer" if m["to"] < m["from"] else "further out"
            parts.append(f'<p style="{body};margin:0 0 8px"><a href="{link(j)}" style="color:{paper}">{e(j["title"])}</a>: {BASE_YEAR + m["from"]} → <span style="color:{gold}">{BASE_YEAR + m["to"]}</span> ({arrow})</p>')
    if scan.get("focus"):
        parts.append(f'<p style="{body};color:{mute};margin:22px 0 0">Sci-fi focus this week: <b style="color:{paper}">{e(scan["focus"])}</b></p>')
    parts.append(f"""<p style="margin:30px 0 0"><a href="{SITE}/" style="display:inline-block;background:{gold};color:{ink};{mono};color:{ink};padding:13px 18px;text-decoration:none">Open the radar · {len(data['jobs'])} jobs</a></p>
<p style="{body};color:{mute};font-size:15px;margin:30px 0 0">Know someone who worries about AI taking their job? Forward this. And reply anytime, I read every message.<br>Marco</p>""")

    addr = CONFIG.get("imprint_address", "").strip()
    footer = f"""<p style="font-family:Arial,sans-serif;font-size:12px;line-height:1.5;color:#6f7899;margin:0">
Not career advice, just a guy from the internet.<br>
You get this because you subscribed on futurejobradar.com. <a href="{{{{ unsubscribe }}}}" style="color:#a9afc6">Unsubscribe</a> · <a href="{SITE}/privacy/" style="color:#a9afc6">Privacy</a><br>
Marco Schmitt{(' · ' + e(addr)) if addr else ''}</p>"""

    html_doc = f"""<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head>
<body style="margin:0;background:{ink}"><table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:{ink}"><tr><td align="center" style="padding:28px 14px">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="max-width:600px"><tr><td>
<p style="{head};font-size:22px;color:{paper};margin:0 0 26px">Future Job <span style="color:{gold}">Radar</span></p>
{''.join(parts)}
<hr style="border:0;border-top:1px solid #2a3256;margin:34px 0 16px">
{footer}
</td></tr></table></td></tr></table></body></html>"""

    subject = f"Job of the week: {cover['title']}" if cover else f"Future Job Radar · Issue {scan['number']}"
    return subject, scan.get("headline", ""), html_doc


def main():
    key, list_id = os.environ.get("BREVO_API_KEY"), os.environ.get("BREVO_LIST_ID")
    data = json.loads(DATA.read_text())
    subject, preview, html_doc = build(data)
    out = ROOT / "reports" / f"newsletter-{data['meta']['scanNumber']:03d}.html"
    out.parent.mkdir(exist_ok=True)
    out.write_text(html_doc)
    print("Newsletter preview written to", out.relative_to(ROOT))
    if not key or not list_id:
        print("BREVO_API_KEY / BREVO_LIST_ID not set: skipping Brevo.")
        return
    mode = (os.environ.get("NEWSLETTER_MODE") or "draft").lower()
    camp = {
        "name": f"Future Job Radar #{data['meta']['scanNumber']}",
        "subject": subject, "previewText": preview[:150],
        "sender": {"name": "Marco · Future Job Radar", "email": os.environ.get("SENDER_EMAIL") or CONFIG["contact_email"]},
        "replyTo": CONFIG["contact_email"],
        "htmlContent": html_doc,
        "recipients": {"listIds": [int(list_id)]},
    }
    if mode == "schedule":
        hhmm = os.environ.get("NEWSLETTER_SEND_UTC") or "09:00"
        camp["scheduledAt"] = f"{datetime.date.today().isoformat()}T{hhmm}:00Z"
    res = brevo("/emailCampaigns", camp, key)
    cid = res.get("id")
    print(f"Brevo campaign {cid} created ({mode}).")
    if mode == "send" and cid:
        brevo(f"/emailCampaigns/{cid}/sendNow", {}, key)
        print("Sent.")


if __name__ == "__main__":
    try:
        main()
    except Exception as ex:  # the newsletter must never break the site build
        print("Newsletter step failed:", ex, file=sys.stderr)
