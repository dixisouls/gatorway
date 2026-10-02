#!/usr/bin/env python3
"""
SFSU Bulletin academic-program scraper.

Starts from https://bulletin.sfsu.edu/programs/, reads the full site nav tree,
crawls every /colleges/... page, and classifies each one:

  program page   has a "Program Requirements" tab (#degreerequirementstextcontainer)
                 and/or a "Roadmap" tab (#roadmaptextcontainer)
  roadmap page   a standalone plan-of-study grid (table.sc_plangrid), child of a program
  other          college / department landing pages (only used for names + link discovery)

The two things that matter are degree requirements and roadmaps. A program is
kept if it has at least one of them; programs with neither (e.g. overview-only
pages) are skipped and listed in the report.

Outputs (in --out):
  sfsu_programs.json            deduplicated programs, each with requirements + roadmaps
  sfsu_program_duplicates.json  same title, different content (for review)
  sfsu_programs_report.json     counts, skipped programs, orphan roadmaps, HTTP failures

Usage:
  python scrap_programs.py                      # full crawl
  python scrap_programs.py --only computer-science   # URLs containing a substring
  python scrap_programs.py --refresh            # ignore HTML cache
"""

import argparse
import hashlib
import json
import re
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup
from tqdm import tqdm

from scrap_courses import BASE, block_lines, clean, fetch, make_session, parse_units

INDEX_URL = f"{BASE}/programs/"

# ---------------------------------------------------------------------------
# URL helpers
# ---------------------------------------------------------------------------

def norm_url(href: str, base: str = INDEX_URL):
    """Absolute, query/fragment-free, trailing-slash URL; None if off-site or not a page."""
    u = urlparse(urljoin(base, href))
    if u.netloc and u.netloc != urlparse(BASE).netloc:
        return None
    path = u.path
    if re.search(r"\.[a-z0-9]{2,5}$", path, re.I):  # .pdf, .png ...
        return None
    if not path.startswith("/colleges/"):
        return None
    if not path.endswith("/"):
        path += "/"
    return f"{BASE}{path}"


def depth(url: str) -> int:
    return len([p for p in urlparse(url).path.split("/") if p])


def is_candidate(url: str) -> bool:
    return depth(url) >= 3  # /colleges/<college>/<dept-or-program>/...

# ---------------------------------------------------------------------------
# Row / table parsing
# ---------------------------------------------------------------------------

def cell_codes(cell) -> list[str]:
    out = []
    for a in cell.select("a.bubblelink"):
        c = clean(a.get("title") or a.get_text(" "))
        if c and c not in out:
            out.append(c)
    return out


def units_fields(raw):
    raw = clean(raw) if raw else None
    if not raw:
        return {"units_raw": None, "units_min": None, "units_max": None}
    lo, hi = parse_units(raw)
    return {"units_raw": raw, "units_min": lo, "units_max": hi}


def parse_requirement_table(table) -> list[dict]:
    rows = []
    for tr in table.find_all("tr"):
        cls = tr.get("class", [])
        if "hidden" in cls:
            continue
        codecell = tr.find("td", class_="codecol")
        hours = tr.find("td", class_="hourscol")
        tds = tr.find_all("td")
        text = clean(tr.get_text(" "))
        if not text:
            continue
        codes = cell_codes(codecell) if codecell else []
        title_td = next((td for td in tds if td is not codecell and td is not hours), None)
        row = {}
        if codes:
            first = clean(codecell.get_text(" "))
            row["type"] = "course"
            row["codes"] = codes
            row["or_with_previous"] = bool("orclass" in cls or re.match(r"^or\b", first, re.I))
            row["title"] = clean(title_td.get_text(" ")) if title_td else None
        else:
            if "areaheader" in cls or "sctablehead" in cls:
                row["type"] = "header"
            elif "listsum" in cls:
                row["type"] = "total"
            else:
                row["type"] = "text"
            row["text"] = clean(" ".join(td.get_text(" ") for td in tds if td is not hours)) or text
        row.update(units_fields(hours.get_text(" ") if hours else None))
        rows.append(row)
    return rows


def parse_plangrid(table) -> dict:
    """One sc_plangrid -> {caption, terms:[{year, term, courses:[...], units_total}]}"""
    cap = table.find("caption")
    grid = {"caption": clean(cap.get_text(" ")) if cap else None, "terms": []}
    term, year = None, None

    def new_term(name):
        nonlocal term
        term = {"year": year, "term": name, "items": [], "units_total": None}
        grid["terms"].append(term)

    for tr in table.find_all("tr"):
        cls = tr.get("class", [])
        if "plangridyear" in cls:
            year = clean(tr.get_text(" "))
            continue
        if "plangridterm" in cls:
            ths = [clean(th.get_text(" ")) for th in tr.find_all("th")]
            name = next((t for t in ths if t and t.lower() != "units"), "")
            new_term(name)
            continue
        tds = tr.find_all("td")
        if not tds:
            continue
        if term is None:
            new_term("")
        hours = tr.find("td", class_="hourscol")
        if "plangridsum" in cls or "plangridtotal" in cls:
            if "plangridsum" in cls:
                term["units_total"] = units_fields(hours.get_text(" ") if hours else None)["units_raw"]
            continue
        codecell = tr.find("td", class_="codecol")
        titlecell = tr.find("td", class_="titlecol")
        item = {}
        footnotes = []
        for scope in (codecell, titlecell):
            if scope is None:
                continue
            for sup in scope.find_all("sup"):
                f = clean(sup.get_text(" "))
                if f:
                    footnotes.append(f)
                sup.decompose()
        codes = cell_codes(codecell) if codecell else []
        tags = []
        if titlecell is not None:
            for sp in titlecell.find_all("span", class_="comment"):
                tags.append(clean(sp.get_text(" ")))
                sp.decompose()
        if codes:
            item["codes"] = codes
            item["title"] = re.sub(r"\(\s*\)", "", clean(titlecell.get_text(" "))).strip() if titlecell else None
            if codecell and re.match(r"^or\b", clean(codecell.get_text(" ")), re.I):
                item["or_with_previous"] = True
        else:
            # generic slot such as "GE Area 4: Social and Behavioral Sciences"
            item["codes"] = []
            item["title"] = clean(" ".join(td.get_text(" ") for td in tds if td is not hours))
        item["tags"] = [t for t in tags if t]
        if footnotes:
            item["footnotes"] = footnotes
        item.update(units_fields(hours.get_text(" ") if hours else None))
        term["items"].append(item)
    return grid

# ---------------------------------------------------------------------------
# Page parsing
# ---------------------------------------------------------------------------

def split_heading(text: str):
    text = clean(text)
    m = re.search(r"\(\s*([^()]*\bunits?\b[^()]*)\)\s*$", text, re.I) or re.search(
        r"[–—-]\s*(\d[\d\s\-–.]*\s*units?)\s*$", text, re.I)
    if m:
        return clean(text[: m.start()]).rstrip("–—- ").strip(), clean(m.group(1))
    return text, None


def parse_requirements(container) -> dict | None:
    """Walk the tab in document order, grouping tables and prose under h2/h3/h4 headings."""
    sections = []
    cur = {"heading": None, "level": 0, "units_raw": None, "notes": [], "rows": []}
    sections.append(cur)
    title_h2 = None

    def walk(node):
        nonlocal cur, title_h2
        for el in node.children:
            name = getattr(el, "name", None)
            if not name:
                continue
            if name in ("h2", "h3", "h4", "h5"):
                heading, units = split_heading(el.get_text(" "))
                if name == "h2" and title_h2 is None:
                    title_h2 = (heading, units)
                    continue
                cur = {"heading": heading, "level": int(name[1]), "units_raw": units, "notes": [], "rows": []}
                sections.append(cur)
            elif name == "table":
                cur["rows"].extend(parse_requirement_table(el))
            elif name in ("ul", "ol", "p", "blockquote"):
                cur["notes"].extend(block_lines(el))
            elif name == "a" or name == "script" or name == "style":
                continue
            elif el.find(["table", "h2", "h3", "h4", "h5"]):
                walk(el)
            else:
                cur["notes"].extend(block_lines(el))

    walk(container)
    sections = [s for s in sections if s["heading"] or s["notes"] or s["rows"]]
    has_content = any(s["rows"] for s in sections)
    if not has_content and not any(s["notes"] for s in sections):
        return None
    name, total = title_h2 if title_h2 else (None, None)
    total_lo = parse_units(total)[0] if total else None
    return {
        "heading": name, "total_units_raw": total, "total_units": total_lo,
        "has_course_tables": has_content,
        "sections": sections,
        "course_codes": sorted({c for s in sections for r in s["rows"] for c in r.get("codes", [])}),
    }


def parse_roadmap_content(container) -> dict | None:
    """Plan-of-study content from a standalone roadmap page or an inline Roadmap tab."""
    grids = [parse_plangrid(t) for t in container.select("table.sc_plangrid")]
    if not grids:
        return None
    # prose around the grids: intro (unit totals etc.) and notes below
    copy = BeautifulSoup(str(container), "lxml")
    for t in copy.find_all("table"):
        t.decompose()
    lines = block_lines(copy)
    full = " ".join(lines)
    tot = re.search(r"(\d+)\s+Total Units Required", full, re.I)
    maj = re.search(r"Minimum Number of Units in the Major:\s*(\d+)", full, re.I)
    return {
        "total_units_required": int(tot.group(1)) if tot else None,
        "major_units": int(maj.group(1)) if maj else None,
        "notes": lines,
        "grids": grids,
    }


def find_tabs(soup):
    """
    Locate the requirements and roadmap tab panels. Container ids differ between pages
    (degreerequirements..., programrequirements..., even a "requriements" typo), so go by
    the tab label and only fall back to id substrings.
    """
    req = rm = None
    for a in soup.find_all("a", href=re.compile(r"^#.+")):
        panel = soup.find(id=a["href"][1:])
        if panel is None:
            continue
        label = clean(a.get_text(" ")).lower()
        if "roadmap" in label and rm is None:
            rm = panel
        elif ("requ" in label or "degree" in label) and req is None:
            req = panel
    if req is None or rm is None:
        for div in soup.find_all("div", id=re.compile(r"textcontainer$")):
            i = div["id"].lower()
            if req is None and "requ" in i:
                req = div
            elif rm is None and "roadmap" in i:
                rm = div
    return req, rm


def parse_page(html: str, url: str) -> dict:
    soup = BeautifulSoup(html, "lxml")
    h1 = soup.find("h1")
    title = clean(h1.get_text(" ")) if h1 else None
    if not title and soup.title:
        title = clean(soup.title.get_text().split("|")[0])

    # every /colleges/ link on the page (nav included) feeds discovery
    links = set()
    for a in soup.find_all("a", href=re.compile(r"^(/|https?://)")):
        n = norm_url(a["href"], url)
        if n and is_candidate(n):
            links.add(n)

    req_c, rm_c = find_tabs(soup)
    main = soup.find(id="textcontainer")

    page = {"url": url, "title": title, "links": sorted(links), "kind": "other",
            "requirements": None, "roadmap_inline": None, "roadmap_links": [], "roadmap_page": None,
            "has_req_tab": req_c is not None, "has_roadmap_tab": rm_c is not None}

    if req_c is None and rm_c is not None and "roadmap" in (title or "").lower():
        # standalone roadmap page that happens to use tabs (e.g. "ADT Roadmap" / "Approved ADTs")
        page["kind"] = "roadmap"
        page["roadmap_page"] = parse_roadmap_content(rm_c)
    elif req_c is not None or rm_c is not None:
        page["kind"] = "program"
        if req_c is not None:
            page["requirements"] = parse_requirements(req_c)
        if rm_c is not None:
            page["roadmap_inline"] = parse_roadmap_content(rm_c)
            rl = []
            for a in rm_c.find_all("a", href=re.compile(r"^(/|https?://)")):
                n = norm_url(a["href"], url)
                if n and n != url and is_candidate(n) and n not in rl:
                    rl.append(n)
            page["roadmap_links"] = rl
        ov = soup.find(id="textcontainer")
        page["overview"] = block_lines(ov) if ov is not None else []
    elif main is not None and main.select_one("table.sc_plangrid"):
        page["kind"] = "roadmap"
        page["roadmap_page"] = parse_roadmap_content(main)
    return page

# ---------------------------------------------------------------------------
# Program metadata from URL / title
# ---------------------------------------------------------------------------

DEGREE_PREFIX = {
    "ba": ("B.A.", "undergraduate"), "bs": ("B.S.", "undergraduate"), "bfa": ("B.F.A.", "undergraduate"),
    "bm": ("B.M.", "undergraduate"), "bsn": ("B.S.N.", "undergraduate"), "bsw": ("B.S.W.", "undergraduate"),
    "ma": ("M.A.", "graduate"), "ms": ("M.S.", "graduate"), "mba": ("M.B.A.", "graduate"),
    "mfa": ("M.F.A.", "graduate"), "mpa": ("M.P.A.", "graduate"), "mph": ("M.P.H.", "graduate"),
    "msw": ("M.S.W.", "graduate"), "mm": ("M.M.", "graduate"), "med": ("M.Ed.", "graduate"),
    "mat": ("M.A.T.", "graduate"), "mpt": ("M.P.T.", "graduate"), "dpt": ("D.P.T.", "graduate"),
    "edd": ("Ed.D.", "graduate"), "dnp": ("D.N.P.", "graduate"), "aud": ("Au.D.", "graduate"),
    "minor": ("Minor", "minor"), "certificate": ("Certificate", "certificate"),
    "ct": ("Certificate", "certificate"), "gct": ("Graduate Certificate", "certificate"),
    "credential": ("Credential", "credential"),
}


def program_meta(url: str, title: str | None, names: dict) -> dict:
    parts = [p for p in urlparse(url).path.split("/") if p]
    college = parts[1] if len(parts) > 1 else None
    dept = parts[2] if len(parts) > 3 else None
    slug = parts[-1]
    first = slug.split("-")[0]
    degree, level = DEGREE_PREFIX.get(first, (None, None))
    if degree is None and "credential" in slug:
        degree, level = "Credential", "credential"
    if degree is None and title:
        t = title.lower()
        for kw, d, lv in (("bachelor", "Bachelor", "undergraduate"), ("master", "Master", "graduate"),
                          ("doctor", "Doctorate", "graduate"), ("minor", "Minor", "minor"),
                          ("certificate", "Certificate", "certificate"), ("credential", "Credential", "credential")):
            if kw in t:
                degree, level = d, lv
                break
    conc = re.search(r"(?:concentration|emphasis|option)\s*(?:in|:)\s*(.+)$", title or "", re.I)
    return {
        "college": names.get(f"{BASE}/colleges/{college}/", college) if college else None,
        "college_slug": college,
        "department": names.get(f"{BASE}/colleges/{college}/{dept}/", dept) if dept else None,
        "department_slug": dept,
        "slug": slug,
        "degree_type": degree,
        "level": level,
        "concentration": clean(conc.group(1)) if conc else None,
    }

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def content_hash(prog) -> str:
    payload = {"req": prog["requirements"], "rm": [r["content"] for r in prog["roadmaps"]]}
    return hashlib.sha1(json.dumps(payload, sort_keys=True, default=str).encode()).hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="sfsu_output")
    ap.add_argument("--cache", default="sfsu_html_cache")
    ap.add_argument("--refresh", action="store_true", help="re-download even if cached")
    ap.add_argument("--delay", type=float, default=0.5, help="seconds before each request")
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--only", nargs="*", help="only crawl URLs containing one of these substrings")
    args = ap.parse_args()

    out = Path(args.out); out.mkdir(parents=True, exist_ok=True)
    cache = Path(args.cache); cache.mkdir(parents=True, exist_ok=True)
    session = make_session()

    print(f"Fetching index {INDEX_URL}")
    soup = BeautifulSoup(fetch(session, INDEX_URL, cache, args.refresh, args.delay), "lxml")
    names, frontier = {}, set()
    for a in soup.find_all("a", href=True):
        n = norm_url(a["href"])
        if n and is_candidate(n):
            frontier.add(n)
        if n and depth(n) <= 3 and n not in names:
            names[n] = clean(a.get_text(" "))
    # college landing pages (depth 2) give the college names
    for a in soup.find_all("a", href=True):
        n = norm_url(a["href"])
        if n and depth(n) == 2:
            names[n] = clean(a.get_text(" "))
    if not frontier:
        sys.exit("No /colleges/ links found on the index page. Site layout may have changed.")
    print(f"Discovered {len(frontier)} candidate pages from the nav tree")

    def keep(u):
        return not args.only or any(s in u for s in args.only)

    pages, errors = {}, {}
    frontier = {u for u in frontier if keep(u)}

    def work(u):
        return parse_page(fetch(session, u, cache, args.refresh, args.delay), u)

    rnd = 0
    while frontier:
        rnd += 1
        batch = sorted(frontier - set(pages))
        frontier = set()
        if not batch:
            break
        with ThreadPoolExecutor(max_workers=args.workers) as ex:
            futs = {ex.submit(work, u): u for u in batch}
            pbar = tqdm(as_completed(futs), total=len(futs), desc=f"Crawl pass {rnd}", unit="page", dynamic_ncols=True)
            for f in pbar:
                u = futs[f]
                try:
                    pages[u] = f.result()
                except Exception as e:
                    errors[u] = repr(e)
                    tqdm.write(f"  ERROR {u}: {e}")
                    continue
                n_prog = sum(1 for p in pages.values() if p["kind"] == "program")
                pbar.set_postfix(programs=n_prog, errors=len(errors))
                for l in pages[u]["links"]:
                    if l not in pages and l not in errors and keep(l):
                        frontier.add(l)
        if rnd > 1:
            tqdm.write(f"  pass {rnd}: {len(batch)} extra pages found beyond the nav tree")

    for u in tqdm(list(errors), desc="Retrying failed", unit="page", disable=not errors):
        try:
            pages[u] = work(u)
            del errors[u]
        except Exception as e:
            errors[u] = repr(e)

    # ---- assemble programs ------------------------------------------------
    roadmap_pages = {u: p for u, p in pages.items() if p["kind"] == "roadmap"}
    claimed = set()
    raw_programs, skipped = [], []

    for u, p in sorted(pages.items()):
        if p["kind"] != "program":
            continue
        has_req = bool(p["requirements"])
        rms = []
        if p["roadmap_inline"]:
            rms.append({"name": "Roadmap (inline)", "source_url": u, "content": p["roadmap_inline"]})
        linked = list(p["roadmap_links"])
        linked += [r for r in roadmap_pages if r.startswith(u) and r != u]  # child pages
        for r in dict.fromkeys(linked):
            if r in roadmap_pages:
                rp = roadmap_pages[r]
                rms.append({"name": rp["title"], "source_url": r, "content": rp["roadmap_page"]})
                claimed.add(r)
        if not has_req and not rms:
            skipped.append({"url": u, "title": p["title"], "has_req_tab": p["has_req_tab"],
                            "has_roadmap_tab": p["has_roadmap_tab"]})
            continue
        prog = {
            "title": p["title"],
            **program_meta(u, p["title"], names),
            "source_url": u,
            "requirements": p["requirements"],
            "roadmaps": rms,
            "overview": p.get("overview", []),
        }
        raw_programs.append(prog)

    orphans = [{"url": u, "title": p["title"]} for u, p in roadmap_pages.items() if u not in claimed]

    # ---- dedupe -----------------------------------------------------------
    # identical (title + content) at different URLs -> merged; same title but different
    # content -> both kept, and flagged in the duplicates file for review
    by_key, dupes, by_title = {}, [], {}
    for prog in raw_programs:
        h = content_hash(prog)
        key = (prog["title"], h)
        if key in by_key:
            by_key[key].setdefault("also_listed_at", []).append(prog["source_url"])
            continue
        prog["_hash"] = h
        by_key[key] = prog
        by_title.setdefault(prog["title"], []).append(prog)
    for title, group in by_title.items():
        if len(group) > 1:
            dupes.append({"title": title, "variants": [g["source_url"] for g in group]})
    programs = sorted(by_key.values(), key=lambda r: (r["college_slug"] or "", r["department_slug"] or "", r["title"] or ""))
    for pr in programs:
        pr.pop("_hash", None)

    report = {
        "pages_crawled": len(pages),
        "program_pages": sum(1 for p in pages.values() if p["kind"] == "program"),
        "roadmap_pages": len(roadmap_pages),
        "programs_kept_raw": len(raw_programs),
        "unique_programs": len(programs),
        "with_requirements": sum(1 for p in programs if p["requirements"]),
        "with_roadmaps": sum(1 for p in programs if p["roadmaps"]),
        "with_both": sum(1 for p in programs if p["requirements"] and p["roadmaps"]),
        "total_roadmaps": sum(len(p["roadmaps"]) for p in programs),
        "same_title_different_content": len(dupes),
        "skipped_no_requirements_or_roadmap": skipped,
        "orphan_roadmap_pages": orphans,
        "requirements_without_course_tables": [p["source_url"] for p in programs
                                                if p["requirements"] and not p["requirements"]["has_course_tables"]],
        "http_errors": errors,
    }

    (out / "sfsu_programs.json").write_text(json.dumps(programs, indent=2, ensure_ascii=False), encoding="utf-8")
    (out / "sfsu_program_duplicates.json").write_text(json.dumps(dupes, indent=2, ensure_ascii=False), encoding="utf-8")
    (out / "sfsu_programs_report.json").write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")

    print("\nDone.")
    print(f"  pages crawled:            {report['pages_crawled']}")
    print(f"  program pages found:      {report['program_pages']}")
    print(f"  unique programs kept:     {report['unique_programs']}  "
          f"(requirements: {report['with_requirements']}, roadmaps: {report['with_roadmaps']}, both: {report['with_both']})")
    print(f"  roadmaps attached:        {report['total_roadmaps']}")
    print(f"  skipped (neither tab):    {len(skipped)}")
    print(f"  orphan roadmap pages:     {len(orphans)}")
    print(f"  same-title conflicts:     {len(dupes)}")
    print(f"  HTTP failures:            {len(errors)}")
    print(f"Output in {out.resolve()}")


if __name__ == "__main__":
    main()
