"""python -m gatorway.ingest [--scrape-dir DIR] [--embeddings gemini|hashing|none]"""
from __future__ import annotations

import argparse
import sys

from sqlalchemy.orm import Session

from gatorway.config import get_settings
from gatorway.db.session import get_engine, init_db

from .embeddings import build_embedder, embed_courses
from .loader import IngestReport, ingest_all, load_scrape_dir


def run(scrape_dir: str, embeddings: str = "gemini", engine=None) -> tuple[IngestReport, int]:
    settings = get_settings()
    engine = engine or get_engine()
    init_db(engine)
    courses, programs = load_scrape_dir(scrape_dir)
    with Session(engine) as db:
        report = ingest_all(db, courses, programs)
        db.commit()
        embedded = 0
        if embeddings != "none":
            embedded = embed_courses(db, build_embedder(embeddings, settings))
    return report, embedded


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="gatorway.ingest")
    ap.add_argument("--scrape-dir", default=get_settings().scrape_dir)
    ap.add_argument("--embeddings", choices=["gemini", "hashing", "none"], default=get_settings().embed_provider)
    args = ap.parse_args(argv)
    report, embedded = run(args.scrape_dir, args.embeddings)
    print(f"courses={report.courses} programs={report.programs} sections={report.sections} roadmaps={report.roadmaps} slots={report.slots}")
    print(f"slots by kind: {report.slots_by_kind}")
    print(f"programs without an elective pool: {report.programs_without_elective_pool}")
    print(f"codes not found in courses: {len(report.unresolved_codes)} {sorted(report.unresolved_codes)[:15]}")
    print(f"courses embedded this run: {embedded}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
