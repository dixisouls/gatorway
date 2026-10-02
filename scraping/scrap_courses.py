#!/usr/bin/env python3
"""
SFSU Bulletin course scraper.

Crawls https://bulletin.sfsu.edu/courses/, discovers every subject page
(ACCT, CSC, MATH, ...), and extracts every course block with:

  course_code, subject, number, title, units_raw, units_min, units_max,
  prerequisites (raw text), prerequisite_courses (parsed codes),
  concurrent_or_coreq (flag + text), repeatable (note), grading,
  course_attributes, description, source_url

Outputs:
  sfsu_courses.json        deduplicated courses
  sfsu_courses.csv         same data, flat
  sfsu_duplicates.json     same course code seen with different content (for review)
  sfsu_scrape_report.json  per-subject counts, parse failures, HTTP failures

Usage:
  pip install requests beautifulsoup4 lxml tqdm
  python sfsu_courses_scraper.py                 # full crawl
  python sfsu_courses_scraper.py --subjects csc math   # only some subjects
  python sfsu_courses_scraper.py --refresh       # ignore HTML cache
"""

import argparse
import csv
import hashlib
import json
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup
from tqdm import tqdm
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

BASE = "https://bulletin.sfsu.edu"
INDEX_URL = f"{BASE}/courses/"
SUBJECT_PATH_RE = re.compile(r"^/courses/([a-z0-9_\-]+)/?$", re.I)

# ---------------------------------------------------------------------------
# HTTP
# ---------------------------------------------------------------------------

def make_session() -> requests.Session:
    s = requests.Session()
    retry = Retry(
        total=6,
        backoff_factor=1.5,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=("GET",),
        respect_retry_after_header=True,
    )
    s.mount("https://", HTTPAdapter(max_retries=retry, pool_maxsize=8))
    s.headers.update({
        "User-Agent": "Mozilla/5.0 (course-catalog research scraper)",
        "Accept": "text/html,application/xhtml+xml",
    })
    return s


def fetch(session, url, cache_dir: Path, refresh: bool, delay: float) -> str:
    key = hashlib.sha1(url.encode()).hexdigest()[:16]
    slug = re.sub(r"[^a-z0-9]+", "_", urlparse(url).path.lower()).strip("_") or "index"
    cache_file = cache_dir / f"{slug}_{key}.html"
    if cache_file.exists() and not refresh:
        return cache_file.read_text(encoding="utf-8")
    time.sleep(delay)
    r = session.get(url, timeout=45)
    r.raise_for_status()
    r.encoding = r.encoding or "utf-8"
    cache_file.write_text(r.text, encoding="utf-8")
    return r.text

# ---------------------------------------------------------------------------
# Text helpers
# ---------------------------------------------------------------------------

def clean(s: str) -> str:
    s = s.replace("\xa0", " ").replace("\u200b", "").replace("\u00ad", "")
    return re.sub(r"\s+", " ", s).strip()


def block_lines(tag) -> list[str]:
    """
    Turn an element into logical lines without breaking on inline links.
    Courseleaf wraps course codes in <a class="bubblelink">, so a naive
    get_text("\\n") would split "CSC 210 or CSC 215" into pieces.
    """
    tag = BeautifulSoup(str(tag), "lxml")  # work on a copy
    for br in tag.find_all("br"):
        br.replace_with("\n")
    for t in tag.find_all(["p", "li", "div", "h1", "h2", "h3", "h4", "h5", "h6", "tr"]):
        t.append("\n")
    raw = tag.get_text("")
    return [clean(x) for x in raw.split("\n") if clean(x)]

# ---------------------------------------------------------------------------
# Subject discovery
# ---------------------------------------------------------------------------

def discover_subjects(html: str) -> dict[str, dict]:
    """Return {slug: {"url":..., "name":..., "code":...}} for every subject page."""
    soup = BeautifulSoup(html, "lxml")
    subjects = {}
    for a in soup.find_all("a", href=True):
        href = urljoin(INDEX_URL, a["href"])
        p = urlparse(href)
        if p.netloc and p.netloc != urlparse(BASE).netloc:
            continue
        m = SUBJECT_PATH_RE.match(p.path)
        if not m:
            continue
        slug = m.group(1).lower()
        text = clean(a.get_text(" "))
        code_m = re.search(r"\(([^()]+)\)\s*$", text)
        code = clean(code_m.group(1)).upper() if code_m else None
        name = clean(text[: code_m.start()]) if code_m else text
        prev = subjects.get(slug)
        # prefer an entry that carries the "(CODE)" form
        if prev is None or (prev["code"] is None and code):
            subjects[slug] = {"url": f"{BASE}/courses/{slug}/", "name": name, "code": code}
    return subjects

# ---------------------------------------------------------------------------
# Course parsing
# ---------------------------------------------------------------------------

TITLE_RE = re.compile(
    r"^(?P<code>(?P<subj>[A-Z][A-Z&/ ]{0,10}?)\s+(?P<num>\d{2,4}[A-Z]{0,3}))\s*[.:]?\s+"
    r"(?P<title>.*?)\s*\(\s*Units?\s*:\s*(?P<units>[^)]*)\)\s*\.?\s*$"
)
# fallback when the "(Units: ...)" part is missing or oddly formatted
TITLE_FALLBACK_RE = re.compile(
    r"^(?P<code>(?P<subj>[A-Z][A-Z&/ ]{0,10}?)\s+(?P<num>\d{2,4}[A-Z]{0,3}))\s*[.:]?\s+(?P<title>.+)$"
)

PREREQ_START_RE = re.compile(
    r"^(pre[\s-]*requisites?|pre[\s-]*or\s+co[\s-]*requisites?|co[\s-]*requisites?|"
    r"recommended\s+preparation|restrictions?|concurrent\s+enrollment)\s*[:.]",
    re.I,
)
ATTR_HEADER_RE = re.compile(r"^course\s+attributes?\s*:?\s*$", re.I)
ATTR_INLINE_RE = re.compile(r"^course\s+attributes?\s*:\s*(.+)$", re.I)
REPEAT_RE = re.compile(r"[^.()]*\bma[y]\s+be\s+repeated\b[^.()]*[.)]?", re.I)
REPEAT_RE2 = re.compile(r"[^.()]*\b(repeatable|not\s+repeatable|may\s+not\s+be\s+repeated)\b[^.()]*[.)]?", re.I)
GRADING_RE = re.compile(
    r"\(?\s*((?:plus[\s-]*minus\s+)?(?:letter\s+grade|ABC/?NC|CR/NC|credit/no\s+credit)[^)\n]*)\)?", re.I
)
CONCURRENT_RE = re.compile(r"concurrent|co[\s-]*requisite|corequisite|simultaneous", re.I)


def parse_units(u: str):
    if not u:
        return None, None
    nums = [float(x) for x in re.findall(r"\d+(?:\.\d+)?", u)]
    if not nums:
        return None, None
    lo, hi = min(nums), max(nums)
    fmt = lambda x: int(x) if x == int(x) else x
    return fmt(lo), fmt(hi)


def build_code_pattern(subject_codes: set[str]):
    # longest first so "MATH" wins over "MA", tolerate missing / non-breaking space
    codes = sorted({c for c in subject_codes if c}, key=len, reverse=True)
    if not codes:
        return None
    alt = "|".join(re.escape(c).replace(r"\ ", r"\s?") for c in codes)
    return re.compile(rf"\b({alt})\s?(\d{{2,4}}[A-Z]{{0,3}})\b")


def extract_course_refs(text: str, code_pat) -> list[str]:
    """
    Pull course codes out of prerequisite text.
    Handles shorthand like 'MATH 226, 227, or 228' by carrying the last subject.
    """
    if not text or code_pat is None:
        return []
    refs = []
    for m in code_pat.finditer(text):
        subj = re.sub(r"\s+", " ", m.group(1)).upper()
        refs.append(f"{subj} {m.group(2)}")
        # continuation numbers right after this match
        tail = text[m.end():]
        pos = 0
        while True:
            cm = re.match(r"\s*(?:,\s*(?:or|and)?|/|\bor\b|\band\b)\s*(\d{3,4}[A-Z]{0,3})\b", tail[pos:])
            if not cm:
                break
            refs.append(f"{subj} {cm.group(1)}")
            pos += cm.end()
    seen, out = set(), []
    for r in refs:
        if r not in seen:
            seen.add(r)
            out.append(r)
    return out


def parse_courseblock(block, source_url, page_subject, code_pat):
    title_el = block.find(class_=re.compile(r"courseblocktitle"))
    if title_el is None:
        title_el = block.find(["p", "h3", "h4", "strong"])
    title_text = clean(title_el.get_text(" ")) if title_el else ""

    rec = {
        "course_code": None, "subject": None, "number": None, "title": None,
        "units_raw": None, "units_min": None, "units_max": None,
        "prerequisites": None, "prerequisite_courses": [],
        "concurrent_or_coreq": False, "concurrent_text": None,
        "repeatable": None, "grading": None,
        "course_attributes": [], "description": None,
        "page_subject": page_subject, "source_url": source_url,
        "parse_warnings": [],
    }

    m = TITLE_RE.match(title_text) or TITLE_FALLBACK_RE.match(title_text)
    if m:
        subj = re.sub(r"\s+", " ", m.group("subj")).strip()
        rec["subject"] = subj
        rec["number"] = m.group("num")
        rec["course_code"] = f"{subj} {m.group('num')}"
        rec["title"] = clean(m.group("title"))
        units = m.groupdict().get("units")
        if units is not None:
            rec["units_raw"] = clean(units)
            rec["units_min"], rec["units_max"] = parse_units(units)
        else:
            rec["parse_warnings"].append("units_not_found_in_title")
    else:
        rec["title"] = title_text
        rec["parse_warnings"].append("title_regex_failed")

    # body = everything in the block except the title element
    body = BeautifulSoup(str(block), "lxml")
    t = body.find(class_=re.compile(r"courseblocktitle"))
    if t is not None:
        t.decompose()
    elif title_el is not None:
        first = body.find(title_el.name)
        if first is not None:
            first.decompose()
    lines = block_lines(body)

    prereq_lines, desc_lines, attrs = [], [], []
    in_attrs = False
    for ln in lines:
        if ATTR_HEADER_RE.match(ln):
            in_attrs = True
            continue
        im = ATTR_INLINE_RE.match(ln)
        if im:
            attrs.append(clean(im.group(1)))
            in_attrs = True
            continue
        if in_attrs:
            attrs.append(ln.lstrip("•·-* ").strip())
            continue
        if PREREQ_START_RE.match(ln):
            prereq_lines.append(ln)
        else:
            desc_lines.append(ln)

    if prereq_lines:
        rec["prerequisites"] = " ".join(prereq_lines)
    rec["course_attributes"] = [a for a in attrs if a]
    desc = " ".join(desc_lines).strip()
    rec["description"] = desc or None

    full = " ".join(filter(None, [rec["prerequisites"], desc]))
    rec["prerequisite_courses"] = extract_course_refs(rec["prerequisites"] or "", code_pat)
    conc = [s for s in re.split(r"(?<=[.;])\s+", full) if CONCURRENT_RE.search(s)]
    if conc:
        rec["concurrent_or_coreq"] = True
        rec["concurrent_text"] = " ".join(conc)
    rep = REPEAT_RE.findall(full) or [x.group(0) for x in REPEAT_RE2.finditer(full)]
    if rep:
        rec["repeatable"] = clean(" ".join(rep))
    g = GRADING_RE.search(full)
    if g:
        rec["grading"] = clean(g.group(1))
    if not rec["parse_warnings"]:
        del rec["parse_warnings"]
    return rec


def parse_subject_page(html, url, slug, code_pat):
    soup = BeautifulSoup(html, "lxml")
    # only top level courseblocks (avoid nested matches of courseblocktitle etc.)
    blocks = [
        b for b in soup.find_all(class_=re.compile(r"(^|\s)courseblock(\s|$)"))
        if not b.find_parent(class_=re.compile(r"(^|\s)courseblock(\s|$)"))
    ]
    # independent sanity count: how many "(Units:" titles exist on the page
    title_count = len(soup.find_all(class_=re.compile(r"courseblocktitle")))
    courses = [parse_courseblock(b, url, slug.upper(), code_pat) for b in blocks]
    return courses, len(blocks), title_count

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def content_hash(rec):
    keys = ("title", "units_raw", "prerequisites", "description", "course_attributes")
    return hashlib.sha1(json.dumps([rec.get(k) for k in keys], sort_keys=True).encode()).hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="sfsu_output")
    ap.add_argument("--cache", default="sfsu_html_cache")
    ap.add_argument("--refresh", action="store_true", help="re-download even if cached")
    ap.add_argument("--delay", type=float, default=0.5, help="seconds before each request")
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--subjects", nargs="*", help="limit to these subject slugs, e.g. csc math")
    args = ap.parse_args()

    out = Path(args.out); out.mkdir(parents=True, exist_ok=True)
    cache = Path(args.cache); cache.mkdir(parents=True, exist_ok=True)
    session = make_session()

    print(f"Fetching index {INDEX_URL}")
    index_html = fetch(session, INDEX_URL, cache, args.refresh, args.delay)
    subjects = discover_subjects(index_html)
    if not subjects:
        sys.exit("No subject links found on the index page. Site layout may have changed.")
    print(f"Discovered {len(subjects)} subject pages")

    all_codes = {s["code"] for s in subjects.values() if s["code"]} | {k.upper() for k in subjects}
    code_pat = build_code_pattern(all_codes)

    targets = subjects
    if args.subjects:
        wanted = {s.lower() for s in args.subjects}
        targets = {k: v for k, v in subjects.items() if k in wanted}
        missing = wanted - set(targets)
        if missing:
            print(f"Warning: unknown subject slugs {sorted(missing)}")

    report = {"subjects_discovered": len(subjects), "per_subject": {}, "http_errors": {}, "parse_warnings": []}
    raw_courses = []

    def work(slug, info):
        html = fetch(session, info["url"], cache, args.refresh, args.delay)
        return slug, parse_subject_page(html, info["url"], slug, code_pat)

    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        futs = {ex.submit(work, s, i): s for s, i in sorted(targets.items())}
        pbar = tqdm(as_completed(futs), total=len(futs), desc="Subjects", unit="subj", dynamic_ncols=True)
        for f in pbar:
            slug = futs[f]
            try:
                _, (courses, n_blocks, n_titles) = f.result()
            except Exception as e:
                report["http_errors"][slug] = repr(e)
                tqdm.write(f"  {slug}: ERROR {e}")
                pbar.set_postfix(courses=len(raw_courses), errors=len(report["http_errors"]), last=slug)
                continue
            report["per_subject"][slug] = {
                "courseblocks": n_blocks, "title_elements": n_titles, "parsed": len(courses),
                "mismatch": n_blocks != n_titles or n_blocks != len(courses),
            }
            for c in courses:
                if c.get("parse_warnings"):
                    report["parse_warnings"].append({"slug": slug, "title": c["title"], "warnings": c["parse_warnings"]})
            raw_courses.extend(courses)
            flag = "  <-- check" if (len(courses) == 0 or report["per_subject"][slug]["mismatch"]) else ""
            tqdm.write(f"  {slug.upper():<8} {len(courses):>4} courses{flag}")
            pbar.set_postfix(courses=len(raw_courses), errors=len(report["http_errors"]), last=slug)

    # retry failed subjects once, sequentially
    for slug in tqdm(list(report["http_errors"]), desc="Retrying failed", unit="subj", disable=not report["http_errors"]):
        try:
            _, (courses, n_blocks, n_titles) = work(slug, targets[slug])
            raw_courses.extend(courses)
            report["per_subject"][slug] = {"courseblocks": n_blocks, "title_elements": n_titles,
                                           "parsed": len(courses), "mismatch": n_blocks != len(courses)}
            del report["http_errors"][slug]
            tqdm.write(f"  retry {slug.upper()}: {len(courses)} courses")
        except Exception as e:
            report["http_errors"][slug] = repr(e)

    # dedupe: one record per course code; identical repeats are dropped silently,
    # differing repeats go to the duplicates file for review
    by_code, dupes, no_code = {}, [], []
    for c in raw_courses:
        code = c["course_code"]
        if not code:
            no_code.append(c)
            continue
        h = content_hash(c)
        if code not in by_code:
            c["_hash"] = h
            c["also_listed_on"] = []
            by_code[code] = c
        else:
            kept = by_code[code]
            if c["page_subject"] != kept["page_subject"] and c["page_subject"] not in kept["also_listed_on"]:
                kept["also_listed_on"].append(c["page_subject"])
            if h != kept["_hash"]:
                dupes.append({"course_code": code, "kept": kept["source_url"], "variant": c})

    courses = sorted(by_code.values(), key=lambda r: (r["subject"] or "", r["number"] or ""))
    for c in courses:
        c.pop("_hash", None)
    courses.extend(no_code)  # never drop anything, even if title parsing failed

    report["raw_records"] = len(raw_courses)
    report["unique_courses"] = len(by_code)
    report["records_without_code"] = len(no_code)
    report["conflicting_duplicates"] = len(dupes)
    report["subjects_with_zero_courses"] = [s for s, v in report["per_subject"].items() if v["parsed"] == 0]
    report["subjects_with_count_mismatch"] = [s for s, v in report["per_subject"].items() if v["mismatch"]]

    (out / "sfsu_courses.json").write_text(json.dumps(courses, indent=2, ensure_ascii=False), encoding="utf-8")
    (out / "sfsu_duplicates.json").write_text(json.dumps(dupes, indent=2, ensure_ascii=False), encoding="utf-8")
    (out / "sfsu_scrape_report.json").write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")

    cols = ["course_code", "subject", "number", "title", "units_raw", "units_min", "units_max",
            "prerequisites", "prerequisite_courses", "concurrent_or_coreq", "concurrent_text",
            "repeatable", "grading", "course_attributes", "description",
            "page_subject", "also_listed_on", "source_url", "parse_warnings"]
    with open(out / "sfsu_courses.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        for c in courses:
            row = dict(c)
            for k in ("prerequisite_courses", "course_attributes", "also_listed_on", "parse_warnings"):
                if isinstance(row.get(k), list):
                    row[k] = " | ".join(row[k])
            w.writerow(row)

    print("\nDone.")
    print(f"  subjects scraped:       {len(report['per_subject'])}/{len(targets)}")
    print(f"  raw course blocks:      {report['raw_records']}")
    print(f"  unique courses:         {report['unique_courses']}")
    print(f"  conflicting duplicates: {report['conflicting_duplicates']}")
    print(f"  parse warnings:         {len(report['parse_warnings'])}")
    print(f"  HTTP failures:          {len(report['http_errors'])}")
    if report["subjects_with_zero_courses"]:
        print(f"  subjects with 0 courses: {report['subjects_with_zero_courses']}")
    print(f"Output in {out.resolve()}")


if __name__ == "__main__":
    main()