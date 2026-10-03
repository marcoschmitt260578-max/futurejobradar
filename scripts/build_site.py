"""Build the static Future Job Radar site into docs/.

- docs/index.html      the magazine page (scripts/page_body.html wrapped in a full HTML document)
- docs/jobs/<id>/      one share page per job with its own Open Graph preview (LinkedIn card)
- docs/og/<id>.png     1200x630 share image per job, plus og/home.png
- docs/sitemap.xml, robots.txt, CNAME

Run: python scripts/build_site.py
"""
import html, json, os, re, shutil
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs"
FONTS = ROOT / "scripts" / "fonts"
SITE = os.environ.get("SITE_URL", "https://futurejobradar.com").rstrip("/")
DOMAIN = SITE.split("//")[-1]

SECTOR = {
    "ai": ("AI & Agents", "#8f9bff"), "finance": ("Finance", "#e6ecff"), "robotics": ("Robotics", "#5ee6ff"),
    "mobility": ("Mobility", "#4dffb8"), "built": ("Built World", "#ffd166"), "energy": ("Energy & Climate", "#ff8a4d"),
    "food": ("Food & Farming", "#b5e853"), "space": ("Space", "#c08bff"), "health": ("Health & Bio", "#ff6b7f"),
    "care": ("Care", "#ff9de2"),
}
BG, PAPER, GOLD, MUTE = "#0d1226", "#f3eee3", "#f2c14e", "#a9afc6"
BASE_YEAR = 2026
e = html.escape
CONFIG = json.loads((ROOT / "scripts" / "site_config.json").read_text())

# Web fonts are self-hosted (no request to Google), files come from Fontsource (OFL licence).
WEB_FONTS = [
    ("Big Shoulders Display", "normal", 600, "big-shoulders-display@5/files/big-shoulders-display-latin-600-normal.woff2"),
    ("Big Shoulders Display", "normal", 800, "big-shoulders-display@5/files/big-shoulders-display-latin-800-normal.woff2"),
    ("Big Shoulders Display", "normal", 900, "big-shoulders-display@5/files/big-shoulders-display-latin-900-normal.woff2"),
    ("Newsreader", "normal", 400, "newsreader@5/files/newsreader-latin-400-normal.woff2"),
    ("Newsreader", "normal", 600, "newsreader@5/files/newsreader-latin-600-normal.woff2"),
    ("Newsreader", "italic", 400, "newsreader@5/files/newsreader-latin-400-italic.woff2"),
    ("JetBrains Mono", "normal", 400, "jetbrains-mono@5/files/jetbrains-mono-latin-400-normal.woff2"),
    ("JetBrains Mono", "normal", 600, "jetbrains-mono@5/files/jetbrains-mono-latin-600-normal.woff2"),
]


def web_fonts_css(prefix):
    """Download the woff2 files into docs/fonts/ and return @font-face rules. Empty string if offline."""
    import urllib.request
    out = DOCS / "fonts"
    out.mkdir(exist_ok=True)
    rules = []
    for fam, style, weight, src in WEB_FONTS:
        name = src.rsplit("/", 1)[-1]
        if not (out / name).exists():
            try:
                (out / name).write_bytes(urllib.request.urlopen("https://cdn.jsdelivr.net/npm/@fontsource/" + src, timeout=60).read())
            except Exception as ex:
                print("WARNING: font download failed, falling back to Google Fonts:", ex)
                return ""
        rules.append(f"@font-face{{font-family:'{fam}';font-style:{style};font-weight:{weight};font-display:swap;src:url({prefix}fonts/{name}) format('woff2')}}")
    return "<style>" + "".join(rules) + "</style>\n"


def fill(text):
    return (text.replace("%%NL_ACTION%%", e(CONFIG.get("newsletter_form_url", "")))
                .replace("%%LINKEDIN%%", e(CONFIG.get("linkedin_url", "")))
                .replace("%%EMAIL%%", e(CONFIG.get("contact_email", ""))))


FONT_SOURCES = {
    "BigShoulders-900.ttf": "big-shoulders-display@5/files/big-shoulders-display-latin-900-normal.woff",
    "BigShoulders-800.ttf": "big-shoulders-display@5/files/big-shoulders-display-latin-800-normal.woff",
    "Newsreader-Italic.ttf": "newsreader@5/files/newsreader-latin-400-italic.woff",
    "JetBrainsMono-600.ttf": "jetbrains-mono@5/files/jetbrains-mono-latin-600-normal.woff",
}


def ensure_fonts():
    """Download the open-source fonts (OFL, via Fontsource on jsDelivr) once and convert them to TTF."""
    import io, urllib.request
    from fontTools.ttLib import TTFont
    FONTS.mkdir(parents=True, exist_ok=True)
    for name, src in FONT_SOURCES.items():
        if (FONTS / name).exists():
            continue
        raw = urllib.request.urlopen("https://cdn.jsdelivr.net/npm/@fontsource/" + src, timeout=60).read()
        f = TTFont(io.BytesIO(raw))
        f.flavor = None
        f.save(str(FONTS / name))


def font(name, size):
    return ImageFont.truetype(str(FONTS / name), size)


def wrap(draw, text, fnt, width):
    words, lines, cur = text.split(), [], ""
    for w in words:
        t = (cur + " " + w).strip()
        if draw.textlength(t, font=fnt) <= width:
            cur = t
        else:
            if cur:
                lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


def fit_title(draw, text, width, max_lines=3, start=128, floor=64):
    size = start
    while size >= floor:
        f = font("BigShoulders-900.ttf", size)
        lines = wrap(draw, text.upper(), f, width)
        if len(lines) <= max_lines and len(lines) * size * 0.92 <= 300 and all(draw.textlength(l, font=f) <= width for l in lines):
            return f, lines
        size -= 6
    f = font("BigShoulders-900.ttf", floor)
    return f, wrap(draw, text.upper(), f, width)[:max_lines]


def rings(draw, cx, cy):
    for i, r in enumerate(range(60, 520, 58)):
        draw.ellipse([cx - r, cy - r, cx + r, cy + r], outline=(242, 193, 78, 26 if i % 2 else 40), width=2)


def og_image(path, kicker, title, sub, year, color):
    img = Image.new("RGBA", (1200, 630), BG)
    ov = Image.new("RGBA", img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(ov)
    rings(d, 1080, 120)
    img = Image.alpha_composite(img, ov)
    d = ImageDraw.Draw(img)
    x = 72
    d.ellipse([x, 76, x + 14, 90], fill=color)
    d.text((x + 26, 70), kicker.upper(), font=font("JetBrainsMono-600.ttf", 24), fill=GOLD)
    fy = font("BigShoulders-900.ttf", 150)
    yw = d.textlength(year, font=fy) if year else 0
    f, lines = fit_title(d, title, 1200 - 2 * x - (yw + 40 if year else 0))
    y = 122
    for l in lines:
        d.text((x, y), l, font=f, fill=PAPER)
        y += int(f.size * 0.92)
    if sub:
        y += 22
        fs = font("Newsreader-Italic.ttf", 34)
        sl = wrap(d, sub, fs, 1200 - 2 * x)
        if len(sl) > 2:
            sl = sl[:2]
            while d.textlength(sl[1] + "…", font=fs) > 1200 - 2 * x:
                sl[1] = sl[1].rsplit(" ", 1)[0]
            sl[1] += "…"
        for l in sl:
            y += 6
            d.text((x, y + 10), l, font=fs, fill=MUTE)
            y += 42
    if year:
        d.text((1200 - x - yw, 92), year, font=fy, fill=GOLD)
        fl = font("JetBrainsMono-600.ttf", 20)
        d.text((1200 - x - d.textlength("ARRIVES", font=fl), 70), "ARRIVES", font=fl, fill=MUTE)
    d.line([x, 548, 1200 - x, 548], fill=(243, 238, 227, 60), width=2)
    fb = font("BigShoulders-900.ttf", 40)
    d.text((x, 562), "FUTURE JOB", font=fb, fill=PAPER)
    d.text((x + d.textlength("FUTURE JOB ", font=fb), 562), "RADAR", font=fb, fill=GOLD)
    fm = font("JetBrainsMono-600.ttf", 22)
    d.text((1200 - x - d.textlength(DOMAIN.upper(), font=fm), 576), DOMAIN.upper(), font=fm, fill=MUTE)
    img.convert("RGB").save(path, "PNG", optimize=True)


def year_of(j):
    return "2036+" if j["horizon"] > 10 else str(BASE_YEAR + j["horizon"])


def head(title, desc, url, image):
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<meta name="site-url" content="{SITE}">
<title>{e(title)}</title>
<meta name="description" content="{e(desc)}">
<link rel="canonical" href="{url}">
<meta property="og:type" content="website">
<meta property="og:site_name" content="Future Job Radar">
<meta property="og:title" content="{e(title)}">
<meta property="og:description" content="{e(desc)}">
<meta property="og:url" content="{url}">
<meta property="og:image" content="{image}">
<meta property="og:image:width" content="1200">
<meta property="og:image:height" content="630">
<meta name="twitter:card" content="summary_large_image">
<meta name="author" content="Marco Schmitt">
<link rel="icon" href="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 64 64'%3E%3Crect width='64' height='64' fill='%230d1226'/%3E%3Ccircle cx='32' cy='32' r='22' fill='none' stroke='%23f2c14e' stroke-width='3'/%3E%3Ccircle cx='32' cy='32' r='12' fill='none' stroke='%23f2c14e' stroke-width='3' opacity='.6'/%3E%3Ccircle cx='44' cy='22' r='5' fill='%23f3eee3'/%3E%3C/svg%3E">
<style>html,body{{margin:0;background:#0d1226}}[hidden]{{display:none!important}}img{{max-width:100%}}</style>
"""


def main():
    ensure_fonts()
    data = json.loads((DOCS / "jobs.json").read_text())
    jobs = data["jobs"]
    (DOCS / "og").mkdir(exist_ok=True)
    jobs_dir = DOCS / "jobs"
    if jobs_dir.exists():
        shutil.rmtree(jobs_dir)
    jobs_dir.mkdir()

    # home
    desc = "Jobs that don't exist yet. A weekly radar of future jobs, built from real signals, science fiction and creative thinking."
    og_image(DOCS / "og" / "home.png", f"{len(jobs)} future jobs · updated weekly", "Jobs that don't exist yet.",
             "Part fact. Part fiction. All imagination.", "", GOLD)
    body = fill((ROOT / "scripts" / "page_body.html").read_text())
    body = re.sub(r"<title>.*?</title>\s*", "", body, count=1)
    links = re.findall(r"<link [^>]+>\s*", body[:2000])
    for l in links:
        body = body.replace(l, "", 1)
    fonts = web_fonts_css("")
    font_head = fonts if fonts else "".join(l.strip() + "\n" for l in links)
    page = (head("Future Job Radar · Jobs that don't exist yet", desc, SITE + "/", SITE + "/og/home.png")
            + font_head + "</head>\n<body>\n" + body + "\n</body>\n</html>\n")
    (DOCS / "index.html").write_text(page)

    # privacy & imprint
    import datetime
    addr = CONFIG.get("imprint_address", "").strip()
    legal = fill((ROOT / "scripts" / "privacy.html").read_text())
    legal = legal.replace("%%ADDRESS%%", "<br>".join(e(x.strip()) for x in addr.split(",")) + "<br>" if addr else "")
    legal = legal.replace("%%UPDATED%%", datetime.date.today().strftime("%d %B %Y"))
    (DOCS / "privacy").mkdir(exist_ok=True)
    (DOCS / "privacy" / "index.html").write_text(
        head("Privacy & imprint · Future Job Radar", "Privacy policy and imprint of the Future Job Radar.", SITE + "/privacy/", SITE + "/og/home.png")
        + (web_fonts_css("../") or "")
        + """<style>body{font-family:Newsreader,Georgia,serif;color:#f3eee3;font-size:18px;line-height:1.6}
.legal{max-width:720px;margin:0 auto;padding:48px 16px 80px}.legal a{color:#f2c14e}
.legal h1{font-family:'Big Shoulders Display',Impact,sans-serif;font-weight:900;text-transform:uppercase;font-size:clamp(44px,8vw,72px);line-height:.95;margin:12px 0 6px}
.legal h2{font-family:'Big Shoulders Display',Impact,sans-serif;font-weight:800;text-transform:uppercase;font-size:28px;margin:36px 0 8px;color:#f2c14e}
.kicker,.upd{font-family:'JetBrains Mono',monospace;font-size:12px;letter-spacing:.14em;text-transform:uppercase;color:#a9afc6}
.kicker a{color:#a9afc6;text-decoration:none}li{margin-bottom:8px}</style>
</head>
<body>
""" + legal + "\n</body>\n</html>\n")

    # one share page per job
    urls = [SITE + "/", SITE + "/privacy/"]
    for j in jobs:
        name, color = SECTOR.get(j["sector"], (j["sector"], GOLD))
        og_image(DOCS / "og" / f"{j['id']}.png", name, j["title"], j["trigger"], year_of(j), color)
        url = f"{SITE}/jobs/{j['id']}/"
        urls.append(url)
        title = f"{j['title']} · arrives ~{year_of(j)} · Future Job Radar"
        d = jobs_dir / j["id"]
        d.mkdir()
        (d / "index.html").write_text(
            head(title, j["trigger"] + " " + j["what"], url, f"{SITE}/og/{j['id']}.png")
            + f"""<meta http-equiv="refresh" content="0; url=../../#{j['id']}">
<script>location.replace('../../#{j['id']}')</script>
</head>
<body style="font-family:Georgia,serif;color:#f3eee3;padding:40px 16px;max-width:640px;margin:0 auto">
<p style="font-family:monospace;color:#f2c14e;letter-spacing:.15em">{e(name.upper())}</p>
<h1>{e(j['title'])}</h1>
<p><em>{e(j['trigger'])}</em></p>
<p>{e(j['what'])}</p>
<p><a style="color:#f2c14e" href="../../#{j['id']}">Read the full story on the Future Job Radar</a></p>
</body>
</html>
""")

    (DOCS / "sitemap.xml").write_text('<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
                                      + "".join(f"<url><loc>{u}</loc></url>\n" for u in urls) + "</urlset>\n")
    (DOCS / "robots.txt").write_text(f"User-agent: *\nAllow: /\nSitemap: {SITE}/sitemap.xml\n")
    (DOCS / "CNAME").write_text(DOMAIN + "\n")
    (DOCS / ".nojekyll").write_text("")
    print(f"Built {len(jobs)} job pages for {SITE}")


if __name__ == "__main__":
    main()
