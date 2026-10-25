#!/usr/bin/env python3
"""Build the public gallery page from ``manifest.json``.

One static HTML file, rendered here with every manifest string escaped, so the
page needs no framework and community text can never become markup. The small
inline script only filters cards that already exist. Recorded voices play
straight from their Release asset; designed presets show the recipe the app
renders locally.

    python site/build.py            # writes _site/index.html
"""
from __future__ import annotations

import json
import sys
from html import escape
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
_REPO = "https://github.com/debpalash/omnivoice-gallery"
_APP = "https://github.com/debpalash/VoiceStudio"
_HANDLE_OK = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-")


def _author(author: str) -> str:
    a = escape(author or "")
    if author and author != "VoiceStudio" and len(author) <= 39 and set(author) <= _HANDLE_OK:
        return f'<a href="https://github.com/{a}" rel="noopener">@{a}</a>'
    return a


def _card(item: dict, packs: list[str]) -> str:
    voice = item["type"] == "voice"
    lang = item.get("language", "")
    body = (
        f'<audio controls preload="none" src="{escape(item["audio"]["url"])}"></audio>'
        f'<p class="quote">“{escape(item["audio"].get("ref_text", ""))}”</p>'
        if voice else
        f'<p class="recipe"><code>{escape(item.get("instruct", ""))}</code></p>'
        f'<p class="quote">“{escape(item.get("sample_script", ""))}”</p>'
    )
    return (
        f'<article class="card" data-pack="{escape(" ".join(packs))}" '
        f'data-lang="{escape(lang)}" data-type="{escape(item["type"])}" '
        f'data-search="{escape((item["name"] + " " + lang + " " + item.get("author", "")).lower())}">'
        f'<header><h2>{escape(item["name"])}</h2>'
        f'<span class="tag">{"Recorded" if voice else "Designed"}</span></header>'
        f'<p class="meta">{escape(lang)} · {escape(item["use_case"])}</p>'
        f'{body}'
        f'<p class="credit">{_author(item.get("author", ""))} · {escape(item.get("license", ""))}</p>'
        f'</article>'
    )


def build(manifest: dict) -> str:
    items = manifest["items"]
    packs = manifest.get("packs", [])
    member = {}
    for p in packs:
        for iid in p.get("item_ids", []):
            member.setdefault(iid, []).append(p["id"])
    langs = sorted({it.get("language", "") for it in items if it.get("language")})
    voices = sum(1 for it in items if it["type"] == "voice")
    pack_buttons = "".join(
        f'<button type="button" data-pack="{escape(p["id"])}">{escape(p["name"])}</button>' for p in packs
    )
    lang_options = "".join(f'<option value="{escape(lang)}">{escape(lang)}</option>' for lang in langs)
    # Recorded voices first: they are the cards you can actually listen to.
    ordered = sorted(items, key=lambda it: it["type"] != "voice")
    cards = "".join(_card(it, member.get(it["id"], [])) for it in ordered)
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>VoiceStudio Gallery</title>
<meta name="description" content="Community and designed voices for VoiceStudio, the fully local voice cloning studio.">
<style>
:root {{ --bg:#fafaf9; --fg:#1c1917; --muted:#57534e; --line:#e7e5e4; --card:#fff; --accent:#4f46e5; }}
@media (prefers-color-scheme: dark) {{
  :root {{ --bg:#0c0a09; --fg:#f5f5f4; --muted:#a8a29e; --line:#292524; --card:#1c1917; --accent:#818cf8; }}
}}
* {{ box-sizing:border-box; }}
body {{ margin:0; background:var(--bg); color:var(--fg); font:15px/1.5 system-ui,-apple-system,"Segoe UI",sans-serif; }}
main {{ max-width:1120px; margin:0 auto; padding:40px 16px 64px; }}
h1 {{ font-size:28px; margin:0 0 4px; letter-spacing:-.01em; }}
.lede {{ color:var(--muted); margin:0 0 24px; max-width:60ch; }}
.lede a, .credit a {{ color:var(--accent); }}
.bar {{ display:flex; flex-wrap:wrap; gap:8px; align-items:center; margin-bottom:20px; }}
.bar button, .bar select, .bar input {{ font:inherit; color:var(--fg); background:var(--card); border:1px solid var(--line); border-radius:999px; padding:6px 14px; }}
.bar input {{ flex:1 1 180px; border-radius:8px; }}
.bar select {{ border-radius:8px; }}
.bar button[aria-pressed="true"] {{ background:var(--fg); color:var(--bg); border-color:var(--fg); }}
.grid {{ display:grid; grid-template-columns:repeat(auto-fill,minmax(260px,1fr)); gap:12px; }}
.card {{ background:var(--card); border:1px solid var(--line); border-radius:12px; padding:16px; display:flex; flex-direction:column; gap:6px; min-width:0; }}
.card[hidden] {{ display:none; }}
.card header {{ display:flex; justify-content:space-between; gap:8px; align-items:baseline; }}
.card h2 {{ font-size:16px; margin:0; }}
.tag {{ font-size:12px; color:var(--muted); border:1px solid var(--line); border-radius:999px; padding:0 8px; white-space:nowrap; }}
.meta, .credit {{ margin:0; color:var(--muted); font-size:13px; }}
.quote {{ margin:0; font-size:14px; overflow-wrap:anywhere; }}
.recipe code {{ font-size:12px; color:var(--muted); }}
.recipe {{ margin:0; }}
audio {{ width:100%; height:36px; }}
.credit {{ margin-top:auto; padding-top:6px; }}
.empty {{ color:var(--muted); }}
footer {{ margin-top:32px; color:var(--muted); font-size:13px; }}
</style>
</head>
<body>
<main>
<h1>VoiceStudio Gallery</h1>
<p class="lede">{len(items)} voices for <a href="{_APP}">VoiceStudio</a>, the fully local voice studio: {voices} recorded by the community and {len(items) - voices} designed voices the app renders on your machine. Open <strong>Gallery → Community</strong> in the app to use one, or <a href="{_REPO}/issues/new/choose">submit your own</a>.</p>
<div class="bar" role="toolbar" aria-label="Filter voices">
<button type="button" data-pack="" aria-pressed="true">All</button>{pack_buttons}
<select id="lang" aria-label="Language"><option value="">All languages</option>{lang_options}</select>
<input id="q" type="search" placeholder="Search name, language, author" aria-label="Search">
</div>
<div class="grid" id="grid">{cards}</div>
<p class="empty" id="empty" hidden>No voices match.</p>
<footer>Updated {escape(manifest.get("updated_at", ""))}. Each voice carries its own licence. Recorded voices are the speakers' own, shared with consent. <a href="{_REPO}">Source</a></footer>
</main>
<script>
(() => {{
  let pack = "";
  const cards = [...document.querySelectorAll(".card")];
  const lang = document.getElementById("lang"), q = document.getElementById("q");
  const apply = () => {{
    const term = q.value.trim().toLowerCase();
    let shown = 0;
    for (const c of cards) {{
      const ok = (!pack || c.dataset.pack.split(" ").includes(pack))
        && (!lang.value || c.dataset.lang === lang.value)
        && (!term || c.dataset.search.includes(term));
      c.hidden = !ok; shown += ok;
    }}
    document.getElementById("empty").hidden = shown > 0;
  }};
  for (const b of document.querySelectorAll(".bar button")) b.addEventListener("click", () => {{
    pack = b.dataset.pack;
    for (const o of document.querySelectorAll(".bar button")) o.setAttribute("aria-pressed", o === b);
    apply();
  }});
  lang.addEventListener("change", apply);
  q.addEventListener("input", apply);
}})();
</script>
</body>
</html>
"""


def main(argv: list[str]) -> int:
    manifest = json.loads((_ROOT / "manifest.json").read_text(encoding="utf-8"))
    out = _ROOT / "_site" / "index.html"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(build(manifest), encoding="utf-8")
    print(f"wrote {out.relative_to(_ROOT)} ({len(manifest['items'])} items)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
