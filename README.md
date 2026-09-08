# Secure Supplies — Open Hardware Index

**Live site: https://hardware.securesupplies.us**

The complete public catalogue of Secure Supplies Group / Donatelli LLC open
hardware — every Stanley A. Meyer water fuel cell, VIC, Gas Management System,
gas processor, steam resonator and Hydrogen Hot Rod ECU board we have
published. 200+ projects, 300,000+ views on PCBWay, published 2019 onward.

Gerbers are open. Every board links straight to its PCBWay project page where
anyone can order the bare PCB at PCBWay's price. Secure Supplies sells the
build manuals, wound VIC assemblies, kits and direct build support.

---

## What this repo builds

| Output | Count | Purpose |
|---|---|---|
| `index.html` | 1 | Static searchable grid, every board a real link |
| `b/<id>-<slug>.html` | ~207 | One indexable page per board |
| `c/<slug>.html` | 9 | One page per category |
| `sitemap.xml` | 217 URLs | With image entries for Google Images |
| `feed.xml` | 60 items | RSS for aggregators and hubs |
| `robots.txt` | — | Explicit allow for 10 major crawlers |
| `<key>.txt` | 1 | IndexNow verification key |

## How it stays current — with no input from anyone

`.github/workflows/build.yml` runs `build_site.py`:

- **daily at 02:00 UTC** (09:00 Asia/Bangkok)
- **on every push** to `build_site.py`, `ga_id.txt` or the workflow itself
- **on demand** — Actions → Build hardware index → Run workflow

Each run pulls the live PCBWay member library, regenerates every page, commits
only if something actually changed, then notifies the search engines. Publish a
new board on PCBWay and it is a live, indexed product page the next morning.

## Search coverage

| Engine | Route |
|---|---|
| Google | sitemap ping + Search Console |
| Google Images | `<image:image>` entries in the sitemap |
| Bing | sitemap ping + **IndexNow** (instant) |
| Yahoo | served by Bing |
| DuckDuckGo | served by Bing |
| Yandex · Naver · Seznam | **IndexNow** (instant) |
| Baidu · Apple · Pinterest | explicit `robots.txt` allow |

**IndexNow** submits every URL the moment a build finishes — minutes to
indexing instead of weeks of waiting for a crawl.

## Structured data

- **Product** on every board page — name, image, category, offer pointing at PCBWay
- **BreadcrumbList** — Index › Category › Board
- **ItemList** on the home page — top 100 boards
- **Organization** + **WebSite** with SearchAction — sitelinks search box
- `og:image` / `twitter:image` on every page, so shares and pins carry the board photo

## Internal linking
Each board page links to 8 related boards in its category, its category page,
and the index. That is how crawl equity reaches the long tail instead of
stopping at the home page.

---

## Files

| Path | What |
|---|---|
| `build_site.py` | The generator. Everything is produced from this one file |
| `.github/workflows/build.yml` | Schedule, build, commit, ping |
| `CNAME` | `hardware.securesupplies.us` |
| `ga_id.txt` | *(optional)* GA4 Measurement ID — create it and every page gets tagged |

## Configuration

All at the top of `build_site.py`:

```
SITE          the canonical domain
BMBNO         the PCBWay member id
CATS          category keyword rules — add a board type by adding a regex
SHOP / JOIN   the Patreon shop and join URLs
INDEXNOW_KEY  must match the <key>.txt file the build writes
```

## Adding Google Analytics
Create a file `ga_id.txt` containing only your Measurement ID (`G-XXXXXXXXXX`).
The next build tags all 217 pages. No other change needed.

## DNS
Cloudflare zone `securesupplies.us` → `CNAME hardware → securesupplies.github.io`.
Keep the proxy **DNS-only (grey cloud)** until GitHub has issued the certificate
and *Enforce HTTPS* is ticked. After that you may proxy it (orange) with
SSL/TLS mode **Full** — never Flexible, which causes a redirect loop.

---

Secure Supplies Group / Donatelli LLC · [securesupplies.us](https://securesupplies.us)
24/7 Desk (520) 435-1881 · Fuel Desk (818) 922-4583
