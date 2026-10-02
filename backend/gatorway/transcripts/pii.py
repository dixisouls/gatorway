"""Local PII redaction with GLiNER (nvidia/gliner-PII, from Hugging Face). Runs on this machine before transcript text goes to any LLM.

Fail closed: if the model cannot load or run, `RedactionError` is raised and nothing is passed on unredacted."""
from __future__ import annotations

import logging
import re
import threading
from typing import Any, Callable

log = logging.getLogger(__name__)

DEFAULT_MODEL = "nvidia/gliner-PII"
PERSON = "person"
DEFAULT_PII_LABELS = [PERSON, "student id", "social security number", "email", "phone number", "address", "date of birth"]
OTHER_LABELS = [label for label in DEFAULT_PII_LABELS if label != PERSON]

# Text the extractor needs. If the model ever flags one of these (it has, e.g. "A 3.0" as an ID at low thresholds), it is left alone.
_PROTECTED = [
    re.compile(r"^[A-Z&]{2,5}(?: [A-Z&]{1,4})?\s?\d{1,3}[A-Za-z]{0,3}$"),  # a course code: CSC 101, MATH 226A, ENGL 1A
    re.compile(r"^[A-F][+-]?(?:\s?\d\.\d+)?$|^(?:W|IP|CR|NC|P|NP|I)$"),  # a grade, with or without grade points: B+, A 3.0
    re.compile(r"^(?:fall|spring|summer|winter)\s+\d{4}$", re.I),  # a term
    re.compile(r"universit|college|institute", re.I),  # the institution (the extractor checks the transcript is SFSU's)
]


class RedactionError(RuntimeError):
    pass


def _load_gliner(model_name: str):
    from gliner import GLiNER  # heavy import: only when first needed

    log.info("Loading GLiNER model %s", model_name)
    return GLiNER.from_pretrained(model_name)


class PIIDetector:
    """Finds PII spans. Long text is checked in overlapping chunks of whole lines, so every part of a transcript is read by the model."""

    def __init__(self, model: Any = None, loader: Callable[[], Any] | None = None, model_name: str = DEFAULT_MODEL, max_chars: int = 900, overlap_lines: int = 2):
        self._model, self._loader = model, loader or (lambda: _load_gliner(model_name))
        self.max_chars, self.overlap_lines = max_chars, overlap_lines
        self._lock = threading.Lock()

    def load(self):
        with self._lock:
            if self._model is None:
                try:
                    self._model = self._loader()
                except Exception as e:
                    raise RedactionError(f"could not load the PII model: {e}") from e
        return self._model

    def _chunks(self, text: str) -> list[str]:
        lines, chunks, current = text.split("\n"), [], []
        for line in lines:
            if current and sum(len(x) + 1 for x in current) + len(line) > self.max_chars:
                chunks.append("\n".join(current))
                current = current[-self.overlap_lines :] if self.overlap_lines else []
            current.append(line)
        if current:
            chunks.append("\n".join(current))
        return chunks

    def detect(self, text: str, labels: list[str], threshold: float) -> list[dict]:
        model, seen, found = self.load(), set(), []
        for chunk in self._chunks(text):
            try:
                entities = model.predict_entities(chunk, labels, threshold=threshold)
            except Exception as e:
                raise RedactionError(f"the PII model failed: {e}") from e
            for e in entities:
                key = (e["text"], e["label"])
                if key not in seen:
                    seen.add(key)
                    found.append(e)
        return found


class GlinerRedactor:
    """Replaces every detected span with its label, e.g. "[PERSON]". Names get a second, lower-threshold pass because the model sometimes
    misses a surname or middle name; the other labels use the normal threshold, because a low one flags grades as IDs."""

    def __init__(self, model_name: str = DEFAULT_MODEL, threshold: float = 0.5, person_threshold: float = 0.3, detector: PIIDetector | None = None):
        self._detector = detector or PIIDetector(model_name=model_name)
        self.threshold, self.person_threshold = threshold, person_threshold

    def warm(self) -> None:
        """Load the model ahead of the first transcript. Failures are logged here and raised again at use (fail closed)."""
        try:
            self._detector.load()
        except RedactionError:
            log.exception("PII model failed to load; transcript uploads will be refused until it does")

    @staticmethod
    def _protected(span: str) -> bool:
        span = span.strip()
        return len(span) < 3 or any(p.search(span) for p in _PROTECTED)

    @staticmethod
    def _bridge_names(text: str, names: set[str]) -> set[str]:
        """A name part the model missed between two it found ("Divya [Lakshmi] Iyer") is part of the name too."""
        extra: set[str] = set()
        for a in names:
            for b in names:
                if a == b:
                    continue
                for m in re.finditer(rf"(?<!\w){re.escape(a)}\s+([A-Z][\w'’-]{{1,20}})\s+{re.escape(b)}(?!\w)", text):
                    extra.add(m.group(1))
        return extra

    def redact(self, text: str) -> str:
        if not text.strip():
            return text
        people = self._detector.detect(text, [PERSON], self.person_threshold)
        others = self._detector.detect(text, OTHER_LABELS, self.threshold)
        spans: dict[str, str] = {}
        for e in [*others, *people]:  # a name wins if the same text was found as both
            for part in e["text"].split("\n"):  # PII sits on one line; a span the model runs across lines must not swallow the next line
                if part.strip() and not self._protected(part):
                    spans[part.strip()] = e["label"].upper()
        for part in self._bridge_names(text, {s for s, label in spans.items() if label == PERSON.upper()}):
            if not self._protected(part):
                spans.setdefault(part, PERSON.upper())
        for span in sorted(spans, key=len, reverse=True):  # longest first, so "Jane Marie Doe" goes before "Jane"
            text = re.sub(rf"(?<!\w){re.escape(span)}(?!\w)", f"[{spans[span]}]", text)
        return text
