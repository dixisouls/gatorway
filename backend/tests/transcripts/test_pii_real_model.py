"""Runs the real nvidia/gliner-PII model (cached from Hugging Face; ~10 s to load). Opt in: RUN_GLINER=1 pytest tests/transcripts/test_pii_real_model.py"""
import os

import pytest

from gatorway.transcripts.pii import GlinerRedactor

pytestmark = pytest.mark.skipif(not os.getenv("RUN_GLINER"), reason="set RUN_GLINER=1 to run the real model")

SAMPLE = """San Francisco State University
Official Academic Transcript
Student Name: Divya Lakshmi Iyer      SFSU ID: 923000111
Email: divya.iyer@mail.sfsu.edu       Phone: (415) 555-0123
Date of Birth: 03/14/2002
Address: 1600 Holloway Ave, San Francisco, CA 94132

       Fall 2023
CSC 101 Introduction to Computing A 3.0
MATH 226 Calculus I B+ 4.0
Spring 2024
CSC 215 Intermediate Programming B 4.0
Printed for Divya Iyer
"""


def test_real_model_removes_personal_details_and_keeps_the_academic_record():
    out = GlinerRedactor().redact(SAMPLE)
    for secret in ("Divya", "Lakshmi", "Iyer", "923000111", "divya.iyer@mail.sfsu.edu", "(415) 555-0123", "03/14/2002", "Holloway"):
        assert secret not in out, (secret, out)
    for kept in ("San Francisco State University", "Official Academic Transcript", "Fall 2023", "Spring 2024", "CSC 101 Introduction to Computing A 3.0",
                 "MATH 226 Calculus I B+ 4.0", "CSC 215 Intermediate Programming B 4.0"):
        assert kept in out, (kept, out)
