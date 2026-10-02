import pytest

from gatorway.transcripts.pii import GlinerRedactor, PIIDetector, RedactionError

TEXT = "Name: Jane Marie Doe\nStudent ID: 923456789\nSan Francisco State University\nFall 2023\nCSC 101 Introduction to Computing A 3.0\n"


class FakeModel:
    """Stands in for GLiNER: reports the entities it was told to find, if the label was asked for and the score clears the threshold."""

    def __init__(self, found, error=None):
        self.found, self.error, self.calls = found, error, []

    def predict_entities(self, text, labels, threshold=0.5):
        self.calls.append((text, tuple(labels), threshold))
        if self.error:
            raise self.error
        return [{"text": t, "label": lab, "score": s} for t, lab, s in self.found if lab in labels and s >= threshold and t in text]


def redactor(found, **kw):
    return GlinerRedactor(detector=PIIDetector(model=FakeModel(found), **kw))


def test_detected_pii_is_replaced_by_its_label_everywhere_it_appears():
    out = redactor([("Jane Marie Doe", "person", 0.9), ("923456789", "student id", 1.0)]).redact(TEXT + "Printed for Jane Marie Doe\n")
    assert "Jane" not in out and "923456789" not in out
    assert out.count("[PERSON]") == 2 and "[STUDENT ID]" in out
    assert "CSC 101 Introduction to Computing A 3.0" in out and "San Francisco State University" in out  # what the extractor needs survives


def test_names_are_looked_for_at_a_lower_threshold_than_other_pii():
    model = FakeModel([("DOE", "person", 0.4), ("923456789", "student id", 0.6), ("A 3.0", "student id", 0.4)])
    out = GlinerRedactor(detector=PIIDetector(model=model), threshold=0.5, person_threshold=0.3).redact("DOE, JANE  923456789  CSC 101 A 3.0")
    assert "[PERSON]" in out and "[STUDENT ID]" in out
    assert "A 3.0" in out  # a weak guess at the grade is below the normal threshold, so grades are left alone
    assert {(labels, thr) for _, labels, thr in model.calls} == {(("person",), 0.3), (("student id", "social security number", "email", "phone number", "address", "date of birth"), 0.5)}


def test_it_never_redacts_what_the_extractor_needs_even_when_the_model_guesses_wrong():
    guesses = [("A 3.0", "student id", 0.99), ("CSC 101", "student id", 0.99), ("San Francisco State University", "address", 0.99), ("B+", "person", 0.99),
               ("Fall 2023", "date of birth", 0.99), ("MATH 226A", "person", 0.99)]
    assert redactor(guesses).redact(TEXT + "MATH 226A Calculus B+ 4.0\n") == TEXT + "MATH 226A Calculus B+ 4.0\n"


def test_a_missed_middle_name_between_two_detected_name_parts_is_redacted_too():
    out = redactor([("Divya", "person", 0.9), ("Iyer", "person", 0.9)]).redact("Student Name: Divya Lakshmi Iyer\nCSC 101 A 3.0")
    assert "Lakshmi" not in out and "Divya" not in out and "Iyer" not in out
    assert "CSC 101 A 3.0" in out


def test_a_name_is_only_replaced_as_a_whole_word():
    out = redactor([("Ann", "person", 0.9)]).redact("Ann Smith took Annotated Bibliography. Ann again.")
    assert "Annotated Bibliography" in out and out.count("[PERSON]") == 2


def test_long_transcripts_are_checked_in_overlapping_chunks_so_nothing_past_the_first_chunk_is_missed():
    lines = [f"CSC {100 + i} Course {i} A 3.0" for i in range(200)] + ["Student: Jane Doe"]
    model = FakeModel([("Jane Doe", "person", 0.9)])
    out = GlinerRedactor(detector=PIIDetector(model=model, max_chars=800)).redact("\n".join(lines))
    assert "Jane Doe" not in out and len(model.calls) > 4
    assert all(len(text) <= 1000 for text, _, _ in model.calls)  # no chunk is bigger than the model can read


def test_a_model_that_cannot_load_means_nothing_is_redacted_or_sent():
    def boom():
        raise OSError("model files missing")

    with pytest.raises(RedactionError):
        GlinerRedactor(detector=PIIDetector(loader=boom)).redact(TEXT)


def test_a_model_that_fails_while_predicting_is_an_error_not_a_pass_through():
    with pytest.raises(RedactionError):
        GlinerRedactor(detector=PIIDetector(model=FakeModel([], error=RuntimeError("cuda"))) ).redact(TEXT)


def test_empty_text_needs_no_model():
    model = FakeModel([])
    assert GlinerRedactor(detector=PIIDetector(model=model)).redact("   \n") == "   \n" and model.calls == []


def test_a_detected_span_that_runs_across_lines_never_takes_the_next_line_with_it():
    text = "Address: 1600 Holloway Ave, San Francisco, CA 94132\n\n       Fall 2023\n       CSC 101 Introduction to Computing A 3.0"
    spanning = "1600 Holloway Ave, San Francisco, CA 94132\n\n       Fall 2023"  # the model really does return spans like this
    out = redactor([(spanning, "address", 0.99)]).redact(text)
    assert "Holloway" not in out and "[ADDRESS]" in out
    assert "Fall 2023" in out and "CSC 101 Introduction to Computing A 3.0" in out
