"""Manual end-to-end check against the running API (real Gemini + real extractor).
Usage: venv/bin/python scripts/smoke_e2e.py [--api http://127.0.0.1:8000] [--interest "web development with Next.js"]"""
from __future__ import annotations

import argparse
import io
import sys
import time

import httpx
from reportlab.pdfgen import canvas

DEMO = [
    "San Francisco State University", "Official Transcript - Demo Student",
    "Fall 2023", "CSC 101 Introduction to Computing A 3.0", "MATH 226 Calculus I B+ 4.0", "ENGL 114 Writing A- 3.0",
    "Spring 2024", "CSC 210 Introduction to Computer Programming A 3.0", "CSC 220 Data Structures B 3.0", "MATH 227 Calculus II B 4.0",
]


def demo_pdf() -> bytes:
    buf = io.BytesIO()
    c = canvas.Canvas(buf)
    y = 800
    for line in DEMO:
        c.drawString(60, y, line)
        y -= 18
    c.save()
    return buf.getvalue()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--api", default="http://127.0.0.1:8000")
    ap.add_argument("--interest", default="web development with Next.js")
    ap.add_argument("--program", default="Bachelor of Science in Computer Science")
    args = ap.parse_args()
    with httpx.Client(base_url=args.api, timeout=180) as c:
        print("health:", c.get("/health").json())
        email = f"smoke{int(time.time())}@sfsu.edu"
        tok = c.post("/auth/signup", json={"email": email, "password": "smoke-test-password"}).json()["access_token"]
        h = {"Authorization": f"Bearer {tok}"}
        up = c.post("/transcripts", files={"file": ("demo.pdf", demo_pdf(), "application/pdf")}, headers=h)
        print("transcript:", up.status_code, up.json())
        programs = c.get("/programs", params={"query": args.program, "limit": 5}).json()["programs"]
        if not programs:
            print("no program matched", args.program)
            return 1
        program = programs[0]
        print("program:", program["id"], program["title"])
        res = c.post("/pathways", json={"program_id": program["id"], "interest": args.interest}, headers=h)
        print("pathway:", res.status_code)
        body = res.json()
        if res.status_code != 200:
            print(body)
            return 1
        print("note:", body["note"], "| cached:", body["cached"])
        for a in body["applied"]:
            print(f"  swapped {a['slot_id']} -> {a['new_course_code']} {a['title']}: {a['reason']}")
        for d in body["dropped"]:
            print(f"  rejected {d['edit']['new_course_code']}: {[v['message'] for v in d['violations']]}")
        print("warnings:", body["warnings"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
