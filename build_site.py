#!/usr/bin/env python3
"""
Secure Supplies hardware index — static site generator.
Pulls the live PCBWay library and writes real HTML that search engines can read
without running JavaScript:

  index.html            static grid, every board a real <a> + <img>
  b/<id>-<slug>.html    one indexable page per board, with Product JSON-LD
  c/<slug>.html         one page per category
  sitemap.xml           every URL
  robots.txt            points at the sitemap
"""
import json, re, sys, time, html, urllib.request, pathlib, datetime, concurrent.futures as cf

SITE   = "https://hardware.securesupplies.us"
BMBNO  = "E9AF6EAA-8A83-4F"
API    = ("https://member.pcbway.com/Project/GetProject_ShareProjectList"
          "?callback=cb&bmbno={b}&type=&page={p}")
UA     = {"User-Agent": "Mozilla/5.0 (compatible; SecureSuppliesIndexBot/1.0)"}
SHOP   = "https://www.patreon.com/c/securesupplies/shop"
JOIN   = "https://www.patreon.com/c/securesupplies"
ROOT   = pathlib.Path(__file__).resolve().parent
GA_ID  = (ROOT / "ga_id.txt").read_text().strip() if (ROOT / "ga_id.txt").exists() else ""
INDEXNOW_KEY = "a7f3c91e5b2d4816be0d7c4a9f16e35b"

CATS = [
 ('ECU / Speeduino / Hydrogen Hot Rod', 'ecu-speeduino-hydrogen-hot-rod', r'speeduino|speedunio|hyduino|core8|teensy|can hub|canpico|egt|map/baro|miata|honda|m50|m52|m60|drop bear|ignitor|stim|\becu\b|ardu-stim|molex|dbw|auxiliary outputs',
  "Hydrogen Hot Rod engine management — Speeduino / rusEFI compatible ECUs, adapters, CAN and sensor conditioning for running an engine on gas."),
 ('Steam Resonator & EPG', 'steam-resonator-epg', r'steam resonator|\bepg\b',
  "Steam resonator and Electrical Particle Generator hardware — the thermal and magnetic side of the system."),
 ('Gas Processor & Ionisation', 'gas-processor-ionisation', r'gas processor|led gas processor|led array|optical lens|intake|exhaust|egr|laser|spark pug|spark plug|ozonat',
  "Gas processor and ionisation hardware — LED arrays, optics, intake and EGR conditioning ahead of the burn."),
 ('Water Fuel Cell & Cell Hardware', 'water-fuel-cell-hardware', r'wfc|water fuel cell|cell tubes|tube cell|anode|cathode|spacer|top cap|lower cap|tube holder|resonant cavity|pressure|flash back|fuel line|single cell|6 cell|9 cell|11 cell|cell holder|water body|nano bubble water fuel cell|9 tube',
  "Water Fuel Cell mechanical hardware — tubes, anodes, caps, holders and pressure parts, dimensioned to the original work."),
 ('VIC, Bobbins, Cores & Chokes', 'vic-bobbins-cores-chokes', r'\bvic\b|bobbin|choke|u-core|u core|e core|ballast|balast|balun|impedance|bifilar|transformer',
  "Voltage Intensifier Circuit magnetics — bobbins, cores, chokes and transformer hardware. The step-up stage that makes the cell work."),
 ('Voltrolysis Power & Switch Drivers', 'voltrolysis-power-switch-drivers', r'8xa|9xa|9xb|9xd|9xam|\bscr\b|half bridge|h bridge|switch driver|switching circuit|\beec\b|electron extract|voltrolysis|alternator|power supply|home heater|puharich',
  "High-side / low-side switching and voltrolysis power stages. Where the gated pulse meets the cell."),
 ('GMS Control Cards', 'gms-control-cards', r'\bgms\b|gate tuning|frequency generator|digital control|accelerator|taco|distributor|feedback|safety|voltage card|analog|analogue|pulse frequency|trigger board|auto start|autofill|les banki|injector card|matrix|db 37|k00|k11|k2 |k3 |k7 |k8|k20|solenoid|warning board|sequential gate|variable gate',
  "Gas Management System logic — gating, frequency, sequencing, safety and voltage control cards."),
 ('Energy Harvesting & Experimental', 'energy-harvesting-experimental', r'rectenna|rf power|energy harvesting|\btpu\b|tesla|battery charger|atu-100|magnetic propulsion|dynamysthesis',
  "Energy harvesting and experimental hardware — rectennas, RF harvesters, TPU and bifilar work."),
]
OTHER = ('Other Boards & Parts', 'other-boards-parts', "Secure Supplies open hardware — gerbers published for replication.")

def classify(t):
    tl = (t or "").lower()
    for name, slug, pat, blurb in CATS:
        if re.search(pat, tl):
            return name, slug, blurb
    return OTHER

def slugify(s, n=70):
    s = re.sub(r'[^a-z0-9]+', '-', (s or '').lower()).strip('-')
    return (s[:n].rstrip('-')) or 'board'

def get(url, tries=3, timeout=45):
    last = None
    for i in range(tries):
        try:
            return urllib.request.urlopen(
                urllib.request.Request(url, headers=UA), timeout=timeout
            ).read().decode('utf-8', 'replace')
        except Exception as e:
            last = e
            time.sleep(2 * (i + 1))
    raise last

def fetch_page(p):
    raw = get(API.format(b=BMBNO, p=p))
    return json.loads(raw[raw.index('(') + 1: raw.rindex(')')])

def description_for(url):
    try:
        h = get(url, tries=2, timeout=30)
        m = re.search(r'<div[^>]*class="[^"]*ql-editor[^"]*"[^>]*>(.*?)</div>\s*</div>', h, re.S)
        if not m:
            m = re.search(r'<div[^>]*class="[^"]*ql-editor[^"]*"[^>]*>(.*?)</div>', h, re.S)
        if not m:
            return ""
        t = re.sub(r'<[^>]+>', ' ', m.group(1))
        t = html.unescape(t)
        t = re.sub(r'https?://\S+', ' ', t)
        return re.sub(r'\s+', ' ', t).strip()
    except Exception:
        return ""

def trim(t, n):
    if len(t) <= n:
        return t
    cut = t[:n]
    dot = max(cut.rfind('. '), cut.rfind('! '), cut.rfind('? '))
    return (cut[:dot + 1] if dot > n * 0.5 else cut.rstrip() + '…')

# ------------------------------------------------------------------ shell ---
CSS = """:root{--navy:#001E50;--navy3:#003278;--ink:#282828;--bg:#f5f6f8;--card:#fff;--line:#e2e5ea;--mut:#5b6472}
@media(prefers-color-scheme:dark){:root{--bg:#141618;--card:#1d2024;--line:#2c3138;--ink:#e9ecf1;--mut:#9aa4b2}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.6 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif}
a{color:var(--navy3)}@media(prefers-color-scheme:dark){a{color:#7fa5e6}}
header{background:linear-gradient(135deg,var(--navy),var(--navy3));color:#fff;padding:26px 0 22px}
header a{color:#fff}.wrap{max-width:1280px;margin:0 auto;padding:0 20px}
h1{margin:0 0 5px;font-size:23px}h2{font-size:18px;margin:26px 0 10px}
.sub{opacity:.87;font-size:13.5px;max-width:72ch}
.kpis{display:flex;gap:26px;margin-top:14px;flex-wrap:wrap}
.kpi b{display:block;font-size:21px;line-height:1.1}.kpi span{font-size:11px;opacity:.8;text-transform:uppercase;letter-spacing:.7px}
.cta{margin-top:16px;display:flex;gap:10px;flex-wrap:wrap}
.cta a{background:#fff;color:var(--navy);text-decoration:none;padding:9px 15px;border-radius:6px;font-weight:600;font-size:13px}
.cta a.alt{background:rgba(255,255,255,.14);color:#fff;border:1px solid rgba(255,255,255,.38)}
.tools{position:sticky;top:0;z-index:5;background:var(--bg);border-bottom:1px solid var(--line);padding:12px 0}
input[type=search]{width:100%;max-width:440px;padding:10px 13px;border:1px solid var(--line);border-radius:7px;background:var(--card);color:var(--ink);font-size:14px}
.chips{display:flex;gap:7px;flex-wrap:wrap;margin-top:10px}
.chip{border:1px solid var(--line);background:var(--card);color:var(--mut);padding:5px 11px;border-radius:20px;font-size:12.5px;text-decoration:none;display:inline-block}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(238px,1fr));gap:16px;padding:18px 0 46px}
.card{background:var(--card);border:1px solid var(--line);border-radius:9px;overflow:hidden;display:flex;flex-direction:column;text-decoration:none;color:inherit}
.card:hover{border-color:var(--navy3);box-shadow:0 4px 14px rgba(0,30,80,.13)}
.card img{width:100%;height:158px;object-fit:cover;background:#0d0f12;display:block}
.bd{padding:11px 12px 13px;display:flex;flex-direction:column;gap:6px;flex:1}
.cat{font-size:10.5px;text-transform:uppercase;letter-spacing:.6px;color:var(--navy3);font-weight:700}
@media(prefers-color-scheme:dark){.cat{color:#7fa5e6}}
.tt{font-size:13.5px;font-weight:600;line-height:1.35}
.meta{margin-top:auto;font-size:11.5px;color:var(--mut);display:flex;justify-content:space-between}
.count{padding:10px 0 0;font-size:13px;color:var(--mut)}
article{max-width:820px}article img{width:100%;max-width:560px;border-radius:9px;border:1px solid var(--line)}
.buy{display:inline-block;background:var(--navy);color:#fff;text-decoration:none;padding:12px 20px;border-radius:7px;font-weight:600;margin:14px 12px 0 0}
.buy.alt{background:transparent;color:var(--navy3);border:1px solid var(--line)}
.crumb{font-size:12.5px;color:var(--mut);padding:14px 0 0}
footer{border-top:1px solid var(--line);padding:20px 0 40px;font-size:12.5px;color:var(--mut);margin-top:30px}
"""

def ga():
    if not GA_ID:
        return ""
    return ('<script async src="https://www.googletagmanager.com/gtag/js?id=%s"></script>'
            '<script>window.dataLayer=window.dataLayer||[];function gtag(){dataLayer.push(arguments)}'
            'gtag("js",new Date());gtag("config","%s");</script>') % (GA_ID, GA_ID)

def shell(title, desc, canonical, body, jsonld=None, extra_head="", image=None):
    if isinstance(jsonld, list):
        ld = ''.join('<script type="application/ld+json">%s</script>' % json.dumps(j, separators=(',', ':')) for j in jsonld)
    else:
        ld = ('<script type="application/ld+json">%s</script>' % json.dumps(jsonld, separators=(',', ':'))) if jsonld else ''
    img = ('<meta property="og:image" content="%s">\n<meta name="twitter:image" content="%s">\n' % (image, image)) if image else ''
    return f"""<!doctype html><html lang="en"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{html.escape(title)}</title>
<meta name="description" content="{html.escape(desc)}">
<link rel="canonical" href="{canonical}">
<meta property="og:title" content="{html.escape(title)}">
<meta property="og:description" content="{html.escape(desc)}">
<meta property="og:url" content="{canonical}">
<meta property="og:type" content="website">
<meta property="og:site_name" content="Secure Supplies Open Hardware">
<meta name="twitter:card" content="summary_large_image">
{img}<link rel="alternate" type="application/rss+xml" title="Secure Supplies Open Hardware" href="{SITE}/feed.xml">
<meta name="robots" content="index,follow,max-image-preview:large,max-snippet:-1,max-video-preview:-1">
{extra_head}<style>{CSS}</style>{ga()}{ld}</head><body>
{body}
<footer><div class="wrap">Secure Supplies Group / Donatelli LLC ·
<a href="https://securesupplies.us">securesupplies.us</a> · 24/7 Desk (520) 435-1881 ·
Fuel Desk (818) 922-4583 · <a href="{SITE}/sitemap.xml">Sitemap</a></div></footer>
</body></html>"""

def rss(boards, today):
    items = []
    for b in boards[:60]:
        items.append(
            "<item><title>%s</title><link>%s%s</link><guid isPermaLink=\"true\">%s%s</guid>"
            "<description>%s</description><category>%s</category></item>"
            % (html.escape(b["title"]), SITE, b["path"], SITE, b["path"],
               html.escape(trim(b.get("desc") or b["cblurb"], 300)), html.escape(b["cat"])))
    return ('<?xml version="1.0" encoding="UTF-8"?>\n'
            '<rss version="2.0"><channel>'
            '<title>Secure Supplies — Open Hardware Index</title>'
            '<link>%s/</link>'
            '<description>Stanley Meyer water fuel cell, VIC, GMS, gas processor and Hydrogen Hot Rod boards. '
            'Gerbers open, order direct from PCBWay.</description>'
            '<language>en</language><lastBuildDate>%s</lastBuildDate>%s</channel></rss>'
            % (SITE, today, "".join(items)))


def card(b):
    return (f'<a class="card" href="{SITE}{b["path"]}">'
            f'<img loading="lazy" src="{html.escape(b["image"])}" alt="{html.escape(b["title"])} PCB">'
            f'<div class="bd"><div class="cat">{html.escape(b["cat"])}</div>'
            f'<div class="tt">{html.escape(b["title"])}</div>'
            f'<div class="meta"><span>{b["views"]:,} views</span><span>{b["date"]}</span></div>'
            f'</div></a>')

def main():
    first = fetch_page(1)
    total = first["TotalCount"]
    pages = (total + 11) // 12
    items = list(first["DataList"])
    for p in range(2, pages + 1):
        items += fetch_page(p)["DataList"]
        time.sleep(0.4)

    seen, boards = set(), []
    for it in items:
        if it["Id"] in seen:
            continue
        seen.add(it["Id"])
        title = (it.get("Title") or "").strip()
        cat, cslug, cblurb = classify(title)
        boards.append({
            "id": it["Id"], "title": title,
            "pcb": "https://www.pcbway.com/project/shareproject/%s.html" % it["FileName"],
            "image": (it.get("CoverPic") or it.get("Pics") or "").split("?")[0],
            "views": it.get("Views", 0), "date": (it.get("AddDate") or "")[:10],
            "cat": cat, "cslug": cslug, "cblurb": cblurb,
            "path": "/b/%d-%s.html" % (it["Id"], slugify(title)),
        })
    boards.sort(key=lambda b: -b["views"])
    if len(boards) < 100:
        print("REFUSING: only %d boards" % len(boards), file=sys.stderr)
        sys.exit(1)

    with cf.ThreadPoolExecutor(max_workers=6) as ex:
        for b, d in zip(boards, ex.map(lambda x: description_for(x["pcb"]), boards)):
            b["desc"] = d

    (ROOT / "b").mkdir(exist_ok=True)
    (ROOT / "c").mkdir(exist_ok=True)
    today = datetime.date.today().isoformat()
    urls = [(SITE + "/", "1.0", None, None)]  # image filled after boards load

    # ---- board pages
    for b in boards:
        long = trim(b["desc"], 1500) or (
            f'{b["title"]} — open hardware from the Secure Supplies library. '
            f'Gerbers are published on PCBWay; order the bare board direct.')
        meta = trim(b["desc"], 155) or f'{b["title"]} — gerbers and PCB, order direct from PCBWay.'
        paras = "".join('<p>%s</p>' % html.escape(x) for x in re.split(r'(?<=[.!?]) (?=[A-Z])', long) if x.strip())
        related = [r for r in boards if r["cslug"] == b["cslug"] and r["id"] != b["id"]][:8]
        rel_html = ("".join('<li><a href="%s%s">%s</a></li>' % (SITE, r["path"], html.escape(r["title"])) for r in related))
        crumbs = {"@context": "https://schema.org", "@type": "BreadcrumbList", "itemListElement": [
            {"@type": "ListItem", "position": 1, "name": "Open Hardware Index", "item": SITE + "/"},
            {"@type": "ListItem", "position": 2, "name": b["cat"], "item": "%s/c/%s.html" % (SITE, b["cslug"])},
            {"@type": "ListItem", "position": 3, "name": b["title"], "item": SITE + b["path"]}]}
        jsonld = {"@context": "https://schema.org", "@type": "Product",
                  "name": b["title"], "image": [b["image"]], "description": meta,
                  "brand": {"@type": "Brand", "name": "Secure Supplies"},
                  "category": b["cat"], "url": SITE + b["path"],
                  "offers": {"@type": "Offer", "url": b["pcb"], "availability": "https://schema.org/InStock",
                             "seller": {"@type": "Organization", "name": "PCBWay"}}}
        body = f"""<header><div class="wrap"><a href="{SITE}/">Secure Supplies — Open Hardware Index</a></div></header>
<div class="wrap"><div class="crumb"><a href="{SITE}/">Index</a> › <a href="{SITE}/c/{b['cslug']}.html">{html.escape(b['cat'])}</a></div>
<article><h1>{html.escape(b['title'])}</h1>
<p class="count">{b['cat']} · {b['views']:,} views on PCBWay · published {b['date']}</p>
<img src="{html.escape(b['image'])}" alt="{html.escape(b['title'])} printed circuit board">
{paras}
<p><a class="buy" href="{b['pcb']}" rel="noopener">Order this board on PCBWay →</a>
<a class="buy alt" href="{SHOP}" rel="noopener">Manuals &amp; kits</a>
<a class="buy alt" href="{JOIN}" rel="noopener">Schematics &amp; build support</a></p>
<h2>About this board</h2>
<p>{html.escape(b['cblurb'])} The gerbers are open — order one board or fifty, at PCBWay's price. Secure Supplies sells the build manuals, wound VIC assemblies, kits and direct build support.</p>
<h2>More {html.escape(b['cat'])}</h2>
<ul>{rel_html}</ul>
<p><a href="{SITE}/c/{b['cslug']}.html">All {html.escape(b['cat'])} →</a> &nbsp;|&nbsp; <a href="{SITE}/">Full hardware index →</a></p>
</article></div>"""
        (ROOT / b["path"].lstrip("/")).write_text(
            shell(f'{b["title"]} — Gerbers & PCB | Secure Supplies', meta, SITE + b["path"], body,
                  [jsonld, crumbs], image=b["image"]),
            encoding="utf-8")
        urls.append((SITE + b["path"], "0.8", b["image"], b["title"]))

    # ---- category pages
    cats = {}
    for b in boards:
        cats.setdefault((b["cat"], b["cslug"], b["cblurb"]), []).append(b)
    for (cname, cslug, cblurb), bs in cats.items():
        body = f"""<header><div class="wrap"><a href="{SITE}/">Secure Supplies — Open Hardware Index</a>
<h1>{html.escape(cname)}</h1><p class="sub">{html.escape(cblurb)}</p></div></header>
<div class="wrap"><p class="count">{len(bs)} boards</p><div class="grid">{"".join(card(x) for x in bs)}</div></div>"""
        (ROOT / "c" / (cslug + ".html")).write_text(
            shell(f'{cname} — Stanley Meyer Open Hardware | Secure Supplies',
                  trim(cblurb, 155), f'{SITE}/c/{cslug}.html', body), encoding="utf-8")
        urls.append((f'{SITE}/c/{cslug}.html', "0.7", None, None))

    # ---- home
    chips = "".join(f'<a class="chip" href="{SITE}/c/{s}.html">{html.escape(n)} ({len(v)})</a>'
                    for (n, s, _), v in sorted(cats.items(), key=lambda kv: -len(kv[1])))
    itemlist = {"@context": "https://schema.org", "@type": "ItemList",
                "itemListElement": [{"@type": "ListItem", "position": i + 1, "url": SITE + b["path"],
                                     "name": b["title"]} for i, b in enumerate(boards[:100])]}
    body = f"""<header><div class="wrap">
<h1>Secure Supplies — Open Hardware Index</h1>
<p class="sub">Every Stanley A. Meyer water fuel cell, VIC, gas management, gas processor, steam resonator and Hydrogen Hot Rod board we have published. Gerbers are open — order any bare PCB or printed part direct from PCBWay at their price, not ours.</p>
<div class="kpis"><div class="kpi"><b>{len(boards)}</b><span>Projects</span></div>
<div class="kpi"><b>{sum(b['views'] for b in boards):,}</b><span>Total views</span></div>
<div class="kpi"><b>{len(cats)}</b><span>Categories</span></div>
<div class="kpi"><b>{today}</b><span>Updated</span></div></div>
<div class="cta"><a href="{SHOP}" rel="noopener">Manuals · Kits · Assembled hardware</a>
<a class="alt" href="{JOIN}" rel="noopener">Schematics &amp; build support</a>
<a class="alt" href="https://www.pcbway.com/project/member/?bmbno={BMBNO}" rel="noopener">PCBWay profile</a></div>
</div></header>
<div class="tools"><div class="wrap"><input type="search" id="q" placeholder="Search {len(boards)} boards — VIC, 8XA, gas processor, speeduino…">
<div class="chips">{chips}</div><div class="count" id="count">{len(boards)} boards</div></div></div>
<div class="wrap"><div class="grid" id="grid">{"".join(card(b) for b in boards)}</div></div>
<script>
const cards=[...document.querySelectorAll('#grid .card')].map(el=>({{el,t:el.innerText.toLowerCase()}}));
document.getElementById('q').oninput=e=>{{const q=e.target.value.toLowerCase();let n=0;
cards.forEach(c=>{{const s=!q||c.t.includes(q);c.el.style.display=s?'':'none';if(s)n++;}});
document.getElementById('count').textContent=n+' of {len(boards)} boards';}};
</script>"""
    org = {"@context": "https://schema.org", "@type": "Organization",
           "name": "Secure Supplies Group", "alternateName": "Secure Supplies Group / Donatelli LLC",
           "url": SITE + "/", "telephone": "+1-520-435-1881",
           "sameAs": ["https://securesupplies.us", JOIN,
                      "https://www.pcbway.com/project/member/?bmbno=" + BMBNO]}
    website = {"@context": "https://schema.org", "@type": "WebSite",
               "name": "Secure Supplies Open Hardware Index", "url": SITE + "/",
               "potentialAction": {"@type": "SearchAction",
                                   "target": SITE + "/?q={search_term_string}",
                                   "query-input": "required name=search_term_string"}}
    (ROOT / "index.html").write_text(
        shell("Secure Supplies — Open Hardware Index | Stanley Meyer PCBs, Gerbers & 3D Parts",
              f"{len(boards)} open hardware boards, gerbers and printed parts — Stanley Meyer water fuel cell, VIC, GMS, gas processor and Hydrogen Hot Rod ECU. Order any bare PCB direct from PCBWay.",
              SITE + "/", body, [itemlist, org, website],
              image=boards[0]["image"] if boards else None), encoding="utf-8")

    # ---- sitemap + robots
    sm = ['<?xml version="1.0" encoding="UTF-8"?>',
          '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" '
          'xmlns:image="http://www.google.com/schemas/sitemap-image/1.1">']
    for u, pri, img, cap in urls:
        img_x = ('<image:image><image:loc>%s</image:loc><image:title>%s</image:title></image:image>'
                 % (html.escape(img), html.escape(cap))) if img else ''
        sm.append(f'<url><loc>{u}</loc><lastmod>{today}</lastmod><priority>{pri}</priority>{img_x}</url>')
    sm.append('</urlset>')
    (ROOT / "sitemap.xml").write_text("\n".join(sm), encoding="utf-8")
    (ROOT / "robots.txt").write_text(
        "User-agent: *\nAllow: /\n\n"
        "User-agent: Googlebot\nAllow: /\n\n"
        "User-agent: Googlebot-Image\nAllow: /\n\n"
        "User-agent: Bingbot\nAllow: /\n\n"
        "User-agent: Slurp\nAllow: /\n\n"
        "User-agent: DuckDuckBot\nAllow: /\n\n"
        "User-agent: YandexBot\nAllow: /\n\n"
        "User-agent: Baiduspider\nAllow: /\n\n"
        "User-agent: Applebot\nAllow: /\n\n"
        "User-agent: PinterestBot\nAllow: /\n\n"
        f"Sitemap: {SITE}/sitemap.xml\n", encoding="utf-8")
    (ROOT / "feed.xml").write_text(rss(boards, today), encoding="utf-8")

    # ---- IndexNow: instant submission to Bing, Yandex, Naver, Seznam
    (ROOT / (INDEXNOW_KEY + ".txt")).write_text(INDEXNOW_KEY, encoding="utf-8")
    try:
        payload = json.dumps({
            "host": SITE.replace("https://", ""),
            "key": INDEXNOW_KEY,
            "keyLocation": "%s/%s.txt" % (SITE, INDEXNOW_KEY),
            "urlList": [u for u, _p, _i, _c in urls][:10000],
        }).encode()
        req = urllib.request.Request("https://api.indexnow.org/indexnow", data=payload,
                                     headers={"Content-Type": "application/json; charset=utf-8",
                                              "User-Agent": UA["User-Agent"]})
        with urllib.request.urlopen(req, timeout=30) as r:
            print("IndexNow: HTTP %s for %d urls" % (r.status, len(urls)))
    except Exception as e:
        print("IndexNow ping failed (non-fatal): %s" % e)

    print("built %d board pages, %d category pages, %d sitemap urls"
          % (len(boards), len(cats), len(urls)))

if __name__ == "__main__":
    main()
#!/usr/bin/env python3
"""
Secure Supplies hardware index — static site generator.
Pulls the live PCBWay library and writes real HTML that search engines can read
without running JavaScript:

  index.html            static grid, every board a real <a> + <img>
  b/<id>-<slug>.html    one indexable page per board, with Product JSON-LD
  c/<slug>.html         one page per category
  sitemap.xml           every URL
  robots.txt            points at the sitemap
"""
import json, re, sys, time, html, urllib.request, pathlib, datetime, concurrent.futures as cf

SITE   = "https://hardware.securesupplies.us"
BMBNO  = "E9AF6EAA-8A83-4F"
API    = ("https://member.pcbway.com/Project/GetProject_ShareProjectList"
          "?callback=cb&bmbno={b}&type=&page={p}")
UA     = {"User-Agent": "Mozilla/5.0 (compatible; SecureSuppliesIndexBot/1.0)"}
SHOP   = "https://www.patreon.com/c/securesupplies/shop"
JOIN   = "https://www.patreon.com/c/securesupplies"
ROOT   = pathlib.Path(__file__).resolve().parent
GA_ID  = (ROOT / "ga_id.txt").read_text().strip() if (ROOT / "ga_id.txt").exists() else ""
INDEXNOW_KEY = "a7f3c91e5b2d4816be0d7c4a9f16e35b"

CATS = [
 ('ECU / Speeduino / Hydrogen Hot Rod', 'ecu-speeduino-hydrogen-hot-rod', r'speeduino|speedunio|hyduino|core8|teensy|can hub|canpico|egt|map/baro|miata|honda|m50|m52|m60|drop bear|ignitor|stim|\becu\b|ardu-stim|molex|dbw|auxiliary outputs',
  "Hydrogen Hot Rod engine management — Speeduino / rusEFI compatible ECUs, adapters, CAN and sensor conditioning for running an engine on gas."),
 ('Steam Resonator & EPG', 'steam-resonator-epg', r'steam resonator|\bepg\b',
  "Steam resonator and Electrical Particle Generator hardware — the thermal and magnetic side of the system."),
 ('Gas Processor & Ionisation', 'gas-processor-ionisation', r'gas processor|led gas processor|led array|optical lens|intake|exhaust|egr|laser|spark pug|spark plug|ozonat',
  "Gas processor and ionisation hardware — LED arrays, optics, intake and EGR conditioning ahead of the burn."),
 ('Water Fuel Cell & Cell Hardware', 'water-fuel-cell-hardware', r'wfc|water fuel cell|cell tubes|tube cell|anode|cathode|spacer|top cap|lower cap|tube holder|resonant cavity|pressure|flash back|fuel line|single cell|6 cell|9 cell|11 cell|cell holder|water body|nano bubble water fuel cell|9 tube',
  "Water Fuel Cell mechanical hardware — tubes, anodes, caps, holders and pressure parts, dimensioned to the original work."),
 ('VIC, Bobbins, Cores & Chokes', 'vic-bobbins-cores-chokes', r'\bvic\b|bobbin|choke|u-core|u core|e core|ballast|balast|balun|impedance|bifilar|transformer',
  "Voltage Intensifier Circuit magnetics — bobbins, cores, chokes and transformer hardware. The step-up stage that makes the cell work."),
 ('Voltrolysis Power & Switch Drivers', 'voltrolysis-power-switch-drivers', r'8xa|9xa|9xb|9xd|9xam|\bscr\b|half bridge|h bridge|switch driver|switching circuit|\beec\b|electron extract|voltrolysis|alternator|power supply|home heater|puharich',
  "High-side / low-side switching and voltrolysis power stages. Where the gated pulse meets the cell."),
 ('GMS Control Cards', 'gms-control-cards', r'\bgms\b|gate tuning|frequency generator|digital control|accelerator|taco|distributor|feedback|safety|voltage card|analog|analogue|pulse frequency|trigger board|auto start|autofill|les banki|injector card|matrix|db 37|k00|k11|k2 |k3 |k7 |k8|k20|solenoid|warning board|sequential gate|variable gate',
  "Gas Management System logic — gating, frequency, sequencing, safety and voltage control cards."),
 ('Energy Harvesting & Experimental', 'energy-harvesting-experimental', r'rectenna|rf power|energy harvesting|\btpu\b|tesla|battery charger|atu-100|magnetic propulsion|dynamysthesis',
  "Energy harvesting and experimental hardware — rectennas, RF harvesters, TPU and bifilar work."),
]
OTHER = ('Other Boards & Parts', 'other-boards-parts', "Secure Supplies open hardware — gerbers published for replication.")

def classify(t):
    tl = (t or "").lower()
    for name, slug, pat, blurb in CATS:
        if re.search(pat, tl):
            return name, slug, blurb
    return OTHER

def slugify(s, n=70):
    s = re.sub(r'[^a-z0-9]+', '-', (s or '').lower()).strip('-')
    return (s[:n].rstrip('-')) or 'board'

def get(url, tries=3, timeout=45):
    last = None
    for i in range(tries):
        try:
            return urllib.request.urlopen(
                urllib.request.Request(url, headers=UA), timeout=timeout
            ).read().decode('utf-8', 'replace')
        except Exception as e:
            last = e
            time.sleep(2 * (i + 1))
    raise last

def fetch_page(p):
    raw = get(API.format(b=BMBNO, p=p))
    return json.loads(raw[raw.index('(') + 1: raw.rindex(')')])

def description_for(url):
    try:
        h = get(url, tries=2, timeout=30)
        m = re.search(r'<div[^>]*class="[^"]*ql-editor[^"]*"[^>]*>(.*?)</div>\s*</div>', h, re.S)
        if not m:
            m = re.search(r'<div[^>]*class="[^"]*ql-editor[^"]*"[^>]*>(.*?)</div>', h, re.S)
        if not m:
            return ""
        t = re.sub(r'<[^>]+>', ' ', m.group(1))
        t = html.unescape(t)
        t = re.sub(r'https?://\S+', ' ', t)
        return re.sub(r'\s+', ' ', t).strip()
    except Exception:
        return ""

def trim(t, n):
    if len(t) <= n:
        return t
    cut = t[:n]
    dot = max(cut.rfind('. '), cut.rfind('! '), cut.rfind('? '))
    return (cut[:dot + 1] if dot > n * 0.5 else cut.rstrip() + '…')

# ------------------------------------------------------------------ shell ---
CSS = """:root{--navy:#001E50;--navy3:#003278;--ink:#282828;--bg:#f5f6f8;--card:#fff;--line:#e2e5ea;--mut:#5b6472}
@media(prefers-color-scheme:dark){:root{--bg:#141618;--card:#1d2024;--line:#2c3138;--ink:#e9ecf1;--mut:#9aa4b2}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.6 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif}
a{color:var(--navy3)}@media(prefers-color-scheme:dark){a{color:#7fa5e6}}
header{background:linear-gradient(135deg,var(--navy),var(--navy3));color:#fff;padding:26px 0 22px}
header a{color:#fff}.wrap{max-width:1280px;margin:0 auto;padding:0 20px}
h1{margin:0 0 5px;font-size:23px}h2{font-size:18px;margin:26px 0 10px}
.sub{opacity:.87;font-size:13.5px;max-width:72ch}
.kpis{display:flex;gap:26px;margin-top:14px;flex-wrap:wrap}
.kpi b{display:block;font-size:21px;line-height:1.1}.kpi span{font-size:11px;opacity:.8;text-transform:uppercase;letter-spacing:.7px}
.cta{margin-top:16px;display:flex;gap:10px;flex-wrap:wrap}
.cta a{background:#fff;color:var(--navy);text-decoration:none;padding:9px 15px;border-radius:6px;font-weight:600;font-size:13px}
.cta a.alt{background:rgba(255,255,255,.14);color:#fff;border:1px solid rgba(255,255,255,.38)}
.tools{position:sticky;top:0;z-index:5;background:var(--bg);border-bottom:1px solid var(--line);padding:12px 0}
input[type=search]{width:100%;max-width:440px;padding:10px 13px;border:1px solid var(--line);border-radius:7px;background:var(--card);color:var(--ink);font-size:14px}
.chips{display:flex;gap:7px;flex-wrap:wrap;margin-top:10px}
.chip{border:1px solid var(--line);background:var(--card);color:var(--mut);padding:5px 11px;border-radius:20px;font-size:12.5px;text-decoration:none;display:inline-block}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(238px,1fr));gap:16px;padding:18px 0 46px}
.card{background:var(--card);border:1px solid var(--line);border-radius:9px;overflow:hidden;display:flex;flex-direction:column;text-decoration:none;color:inherit}
.card:hover{border-color:var(--navy3);box-shadow:0 4px 14px rgba(0,30,80,.13)}
.card img{width:100%;height:158px;object-fit:cover;background:#0d0f12;display:block}
.bd{padding:11px 12px 13px;display:flex;flex-direction:column;gap:6px;flex:1}
.cat{font-size:10.5px;text-transform:uppercase;letter-spacing:.6px;color:var(--navy3);font-weight:700}
@media(prefers-color-scheme:dark){.cat{color:#7fa5e6}}
.tt{font-size:13.5px;font-weight:600;line-height:1.35}
.meta{margin-top:auto;font-size:11.5px;color:var(--mut);display:flex;justify-content:space-between}
.count{padding:10px 0 0;font-size:13px;color:var(--mut)}
article{max-width:820px}article img{width:100%;max-width:560px;border-radius:9px;border:1px solid var(--line)}
.buy{display:inline-block;background:var(--navy);color:#fff;text-decoration:none;padding:12px 20px;border-radius:7px;font-weight:600;margin:14px 12px 0 0}
.buy.alt{background:transparent;color:var(--navy3);border:1px solid var(--line)}
.crumb{font-size:12.5px;color:var(--mut);padding:14px 0 0}
footer{border-top:1px solid var(--line);padding:20px 0 40px;font-size:12.5px;color:var(--mut);margin-top:30px}
"""

def ga():
    if not GA_ID:
        return ""
    return ('<script async src="https://www.googletagmanager.com/gtag/js?id=%s"></script>'
            '<script>window.dataLayer=window.dataLayer||[];function gtag(){dataLayer.push(arguments)}'
            'gtag("js",new Date());gtag("config","%s");</script>') % (GA_ID, GA_ID)

def shell(title, desc, canonical, body, jsonld=None, extra_head="", image=None):
    if isinstance(jsonld, list):
        ld = ''.join('<script type="application/ld+json">%s</script>' % json.dumps(j, separators=(',', ':')) for j in jsonld)
    else:
        ld = ('<script type="application/ld+json">%s</script>' % json.dumps(jsonld, separators=(',', ':'))) if jsonld else ''
    img = ('<meta property="og:image" content="%s">\n<meta name="twitter:image" content="%s">\n' % (image, image)) if image else ''
    return f"""<!doctype html><html lang="en"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{html.escape(title)}</title>
<meta name="description" content="{html.escape(desc)}">
<link rel="canonical" href="{canonical}">
<meta property="og:title" content="{html.escape(title)}">
<meta property="og:description" content="{html.escape(desc)}">
<meta property="og:url" content="{canonical}">
<meta property="og:type" content="website">
<meta property="og:site_name" content="Secure Supplies Open Hardware">
<meta name="twitter:card" content="summary_large_image">
{img}<meta name="robots" content="index,follow,max-image-preview:large,max-snippet:-1,max-video-preview:-1">
{extra_head}<style>{CSS}</style>{ga()}{ld}</head><body>
{body}
<footer><div class="wrap">Secure Supplies Group / Donatelli LLC ·
<a href="https://securesupplies.us">securesupplies.us</a> · 24/7 Desk (520) 435-1881 ·
Fuel Desk (818) 922-4583 · <a href="{SITE}/sitemap.xml">Sitemap</a></div></footer>
</body></html>"""

def rss(boards, today):
    items = []
    for b in boards[:60]:
        items.append(
            "<item><title>%s</title><link>%s%s</link><guid isPermaLink=\"true\">%s%s</guid>"
            "<description>%s</description><category>%s</category></item>"
            % (html.escape(b["title"]), SITE, b["path"], SITE, b["path"],
               html.escape(trim(b.get("desc") or b["cblurb"], 300)), html.escape(b["cat"])))
    return ('<?xml version="1.0" encoding="UTF-8"?>\n'
            '<rss version="2.0"><channel>'
            '<title>Secure Supplies — Open Hardware Index</title>'
            '<link>%s/</link>'
            '<description>Stanley Meyer water fuel cell, VIC, GMS, gas processor and Hydrogen Hot Rod boards. '
            'Gerbers open, order direct from PCBWay.</description>'
            '<language>en</language><lastBuildDate>%s</lastBuildDate>%s</channel></rss>'
            % (SITE, today, "".join(items)))


def card(b):
    return (f'<a class="card" href="{SITE}{b["path"]}">'
            f'<img loading="lazy" src="{html.escape(b["image"])}" alt="{html.escape(b["title"])} PCB">'
            f'<div class="bd"><div class="cat">{html.escape(b["cat"])}</div>'
            f'<div class="tt">{html.escape(b["title"])}</div>'
            f'<div class="meta"><span>{b["views"]:,} views</span><span>{b["date"]}</span></div>'
            f'</div></a>')

def main():
    first = fetch_page(1)
    total = first["TotalCount"]
    pages = (total + 11) // 12
    items = list(first["DataList"])
    for p in range(2, pages + 1):
        items += fetch_page(p)["DataList"]
        time.sleep(0.4)

    seen, boards = set(), []
    for it in items:
        if it["Id"] in seen:
            continue
        seen.add(it["Id"])
        title = (it.get("Title") or "").strip()
        cat, cslug, cblurb = classify(title)
        boards.append({
            "id": it["Id"], "title": title,
            "pcb": "https://www.pcbway.com/project/shareproject/%s.html" % it["FileName"],
            "image": (it.get("CoverPic") or it.get("Pics") or "").split("?")[0],
            "views": it.get("Views", 0), "date": (it.get("AddDate") or "")[:10],
            "cat": cat, "cslug": cslug, "cblurb": cblurb,
            "path": "/b/%d-%s.html" % (it["Id"], slugify(title)),
        })
    boards.sort(key=lambda b: -b["views"])
    if len(boards) < 100:
        print("REFUSING: only %d boards" % len(boards), file=sys.stderr)
        sys.exit(1)

    with cf.ThreadPoolExecutor(max_workers=6) as ex:
        for b, d in zip(boards, ex.map(lambda x: description_for(x["pcb"]), boards)):
            b["desc"] = d

    (ROOT / "b").mkdir(exist_ok=True)
    (ROOT / "c").mkdir(exist_ok=True)
    today = datetime.date.today().isoformat()
    urls = [(SITE + "/", "1.0", None, None)]  # image filled after boards load

    # ---- board pages
    for b in boards:
        long = trim(b["desc"], 1500) or (
            f'{b["title"]} — open hardware from the Secure Supplies library. '
            f'Gerbers are published on PCBWay; order the bare board direct.')
        meta = trim(b["desc"], 155) or f'{b["title"]} — gerbers and PCB, order direct from PCBWay.'
        paras = "".join('<p>%s</p>' % html.escape(x) for x in re.split(r'(?<=[.!?]) (?=[A-Z])', long) if x.strip())
        related = [r for r in boards if r["cslug"] == b["cslug"] and r["id"] != b["id"]][:8]
        rel_html = ("".join('<li><a href="%s%s">%s</a></li>' % (SITE, r["path"], html.escape(r["title"])) for r in related))
        crumbs = {"@context": "https://schema.org", "@type": "BreadcrumbList", "itemListElement": [
            {"@type": "ListItem", "position": 1, "name": "Open Hardware Index", "item": SITE + "/"},
            {"@type": "ListItem", "position": 2, "name": b["cat"], "item": "%s/c/%s.html" % (SITE, b["cslug"])},
            {"@type": "ListItem", "position": 3, "name": b["title"], "item": SITE + b["path"]}]}
        jsonld = {"@context": "https://schema.org", "@type": "Product",
                  "name": b["title"], "image": [b["image"]], "description": meta,
                  "brand": {"@type": "Brand", "name": "Secure Supplies"},
                  "category": b["cat"], "url": SITE + b["path"],
                  "offers": {"@type": "Offer", "url": b["pcb"], "availability": "https://schema.org/InStock",
                             "seller": {"@type": "Organization", "name": "PCBWay"}}}
        body = f"""<header><div class="wrap"><a href="{SITE}/">Secure Supplies — Open Hardware Index</a></div></header>
<div class="wrap"><div class="crumb"><a href="{SITE}/">Index</a> › <a href="{SITE}/c/{b['cslug']}.html">{html.escape(b['cat'])}</a></div>
<article><h1>{html.escape(b['title'])}</h1>
<p class="count">{b['cat']} · {b['views']:,} views on PCBWay · published {b['date']}</p>
<img src="{html.escape(b['image'])}" alt="{html.escape(b['title'])} printed circuit board">
{paras}
<p><a class="buy" href="{b['pcb']}" rel="noopener">Order this board on PCBWay →</a>
<a class="buy alt" href="{SHOP}" rel="noopener">Manuals &amp; kits</a>
<a class="buy alt" href="{JOIN}" rel="noopener">Schematics &amp; build support</a></p>
<h2>About this board</h2>
<p>{html.escape(b['cblurb'])} The gerbers are open — order one board or fifty, at PCBWay's price. Secure Supplies sells the build manuals, wound VIC assemblies, kits and direct build support.</p>
<h2>More {html.escape(b['cat'])}</h2>
<ul>{rel_html}</ul>
<p><a href="{SITE}/c/{b['cslug']}.html">All {html.escape(b['cat'])} →</a> &nbsp;|&nbsp; <a href="{SITE}/">Full hardware index →</a></p>
</article></div>"""
        (ROOT / b["path"].lstrip("/")).write_text(
            shell(f'{b["title"]} — Gerbers & PCB | Secure Supplies', meta, SITE + b["path"], body,
                  [jsonld, crumbs], image=b["image"]),
            encoding="utf-8")
        urls.append((SITE + b["path"], "0.8", b["image"], b["title"]))

    # ---- category pages
    cats = {}
    for b in boards:
        cats.setdefault((b["cat"], b["cslug"], b["cblurb"]), []).append(b)
    for (cname, cslug, cblurb), bs in cats.items():
        body = f"""<header><div class="wrap"><a href="{SITE}/">Secure Supplies — Open Hardware Index</a>
<h1>{html.escape(cname)}</h1><p class="sub">{html.escape(cblurb)}</p></div></header>
<div class="wrap"><p class="count">{len(bs)} boards</p><div class="grid">{"".join(card(x) for x in bs)}</div></div>"""
        (ROOT / "c" / (cslug + ".html")).write_text(
            shell(f'{cname} — Stanley Meyer Open Hardware | Secure Supplies',
                  trim(cblurb, 155), f'{SITE}/c/{cslug}.html', body), encoding="utf-8")
        urls.append((f'{SITE}/c/{cslug}.html', "0.7", None, None))

    # ---- home
    chips = "".join(f'<a class="chip" href="{SITE}/c/{s}.html">{html.escape(n)} ({len(v)})</a>'
                    for (n, s, _), v in sorted(cats.items(), key=lambda kv: -len(kv[1])))
    itemlist = {"@context": "https://schema.org", "@type": "ItemList",
                "itemListElement": [{"@type": "ListItem", "position": i + 1, "url": SITE + b["path"],
                                     "name": b["title"]} for i, b in enumerate(boards[:100])]}
    body = f"""<header><div class="wrap">
<h1>Secure Supplies — Open Hardware Index</h1>
<p class="sub">Every Stanley A. Meyer water fuel cell, VIC, gas management, gas processor, steam resonator and Hydrogen Hot Rod board we have published. Gerbers are open — order any bare PCB or printed part direct from PCBWay at their price, not ours.</p>
<div class="kpis"><div class="kpi"><b>{len(boards)}</b><span>Projects</span></div>
<div class="kpi"><b>{sum(b['views'] for b in boards):,}</b><span>Total views</span></div>
<div class="kpi"><b>{len(cats)}</b><span>Categories</span></div>
<div class="kpi"><b>{today}</b><span>Updated</span></div></div>
<div class="cta"><a href="{SHOP}" rel="noopener">Manuals · Kits · Assembled hardware</a>
<a class="alt" href="{JOIN}" rel="noopener">Schematics &amp; build support</a>
<a class="alt" href="https://www.pcbway.com/project/member/?bmbno={BMBNO}" rel="noopener">PCBWay profile</a></div>
</div></header>
<div class="tools"><div class="wrap"><input type="search" id="q" placeholder="Search {len(boards)} boards — VIC, 8XA, gas processor, speeduino…">
<div class="chips">{chips}</div><div class="count" id="count">{len(boards)} boards</div></div></div>
<div class="wrap"><div class="grid" id="grid">{"".join(card(b) for b in boards)}</div></div>
<script>
const cards=[...document.querySelectorAll('#grid .card')].map(el=>({{el,t:el.innerText.toLowerCase()}}));
document.getElementById('q').oninput=e=>{{const q=e.target.value.toLowerCase();let n=0;
cards.forEach(c=>{{const s=!q||c.t.includes(q);c.el.style.display=s?'':'none';if(s)n++;}});
document.getElementById('count').textContent=n+' of {len(boards)} boards';}};
</script>"""
    org = {"@context": "https://schema.org", "@type": "Organization",
           "name": "Secure Supplies Group", "alternateName": "Secure Supplies Group / Donatelli LLC",
           "url": SITE + "/", "telephone": "+1-520-435-1881",
           "sameAs": ["https://securesupplies.us", JOIN,
                      "https://www.pcbway.com/project/member/?bmbno=" + BMBNO]}
    website = {"@context": "https://schema.org", "@type": "WebSite",
               "name": "Secure Supplies Open Hardware Index", "url": SITE + "/",
               "potentialAction": {"@type": "SearchAction",
                                   "target": SITE + "/?q={search_term_string}",
                                   "query-input": "required name=search_term_string"}}
    (ROOT / "index.html").write_text(
        shell("Secure Supplies — Open Hardware Index | Stanley Meyer PCBs, Gerbers & 3D Parts",
              f"{len(boards)} open hardware boards, gerbers and printed parts — Stanley Meyer water fuel cell, VIC, GMS, gas processor and Hydrogen Hot Rod ECU. Order any bare PCB direct from PCBWay.",
              SITE + "/", body, [itemlist, org, website],
              image=boards[0]["image"] if boards else None), encoding="utf-8")

    # ---- sitemap + robots
    sm = ['<?xml version="1.0" encoding="UTF-8"?>',
          '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" '
          'xmlns:image="http://www.google.com/schemas/sitemap-image/1.1">']
    for u, pri, img, cap in urls:
        img_x = ('<image:image><image:loc>%s</image:loc><image:title>%s</image:title></image:image>'
                 % (html.escape(img), html.escape(cap))) if img else ''
        sm.append(f'<url><loc>{u}</loc><lastmod>{today}</lastmod><priority>{pri}</priority>{img_x}</url>')
    sm.append('</urlset>')
    (ROOT / "sitemap.xml").write_text("\n".join(sm), encoding="utf-8")
    (ROOT / "robots.txt").write_text(
        "User-agent: *\nAllow: /\n\n"
        "User-agent: Googlebot\nAllow: /\n\n"
        "User-agent: Googlebot-Image\nAllow: /\n\n"
        "User-agent: Bingbot\nAllow: /\n\n"
        "User-agent: Slurp\nAllow: /\n\n"
        "User-agent: DuckDuckBot\nAllow: /\n\n"
        "User-agent: YandexBot\nAllow: /\n\n"
        "User-agent: Baiduspider\nAllow: /\n\n"
        "User-agent: Applebot\nAllow: /\n\n"
        "User-agent: PinterestBot\nAllow: /\n\n"
        f"Sitemap: {SITE}/sitemap.xml\n", encoding="utf-8")
    (ROOT / "feed.xml").write_text(rss(boards, today), encoding="utf-8")

    # ---- IndexNow: instant submission to Bing, Yandex, Naver, Seznam
    (ROOT / (INDEXNOW_KEY + ".txt")).write_text(INDEXNOW_KEY, encoding="utf-8")
    try:
        payload = json.dumps({
            "host": SITE.replace("https://", ""),
            "key": INDEXNOW_KEY,
            "keyLocation": "%s/%s.txt" % (SITE, INDEXNOW_KEY),
            "urlList": [u for u, _p, _i, _c in urls][:10000],
        }).encode()
        req = urllib.request.Request("https://api.indexnow.org/indexnow", data=payload,
                                     headers={"Content-Type": "application/json; charset=utf-8",
                                              "User-Agent": UA["User-Agent"]})
        with urllib.request.urlopen(req, timeout=30) as r:
            print("IndexNow: HTTP %s for %d urls" % (r.status, len(urls)))
    except Exception as e:
        print("IndexNow ping failed (non-fatal): %s" % e)

    print("built %d board pages, %d category pages, %d sitemap urls"
          % (len(boards), len(cats), len(urls)))

if __name__ == "__main__":
    main()
