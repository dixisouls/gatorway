# GatorWay — Architecture

Living document. Updated at every design step; sections cross-reference each other
(**Depends on** = look up, **Used by** = look down). Status per section:
`Approved` · `Proposed` (awaiting sign-off) · `Draft`.

Context: **hackathon project, everything runs on one laptop.** Not distributed. A Next.js frontend ([§8](#8-frontend)) talks to the API.

**Contents**
[0 Goal](#0-goal) · [1 Runtime & flows](#1-runtime--request-flows) · [2 Data model](#2-data-model) ·
[3 Ingestion](#3-ingestion-pipeline) · [4 MCP tools & pathway engine](#4-mcp-tools--pathway-engine) ·
[5 API surface](#5-api-surface) · [6 Caching](#6-redis-caching) · [7 Security & privacy](#7-security--privacy) · [8 Frontend](#8-frontend) ·
[Decisions](#decision-log) · [Open questions](#open-questions)

---

## 0. Goal
Status: **Approved**

An SFSU student signs up, uploads a transcript, and states an interest ("web dev with Next.js").
We return their degree roadmap, with **non-core slots swapped** for courses matching the interest.
Core requirements are untouched, passed courses are accounted for, and no prerequisite is skipped.

Used by: everything below. Constraints are recorded in the [Decision log](#decision-log).

---

## 1. Runtime & request flows
Status: **Approved** (hackathon-local runtime: D3, D4)

### 1.1 What runs

| Piece | How | Port |
|---|---|---|
| Postgres 18 + pgvector 0.8.7 | `docker compose`; image `pgvector/pgvector:pg18` (already local; includes `psql`); named volume `gw_pgdata` mounted at `/var/lib/postgresql` (PG 18 layout, `PGDATA=/var/lib/postgresql/18/docker`) | 5432 |
| Redis 8 | `docker compose`; `redis:8-alpine`, `--appendonly yes`, named volume `gw_redisdata` at `/data` | 6379 |
| FastAPI app | `uvicorn` (plain process) | 8000 |
| FastMCP server | `python -m` (plain process, streamable HTTP) | 8001 |
| Transcript extractor | **Google Cloud Run** (stateless; Gemini via Vertex AI) — hackathon requirement | — |

API and MCP share one Python package (DB + domain logic) — no duplicated code. The extractor is a separate small deploy folder.
`frontend/` holds the Next.js web app ([§8](#8-frontend)).

### 1.2 Flow A — transcript upload
`POST /transcripts` (PDF) →
1. **Local PDF→text.** Nothing extractable (e.g. a scanned image) ⇒ rejected; there is no OCR (D13).
2. **`Redactor` port** (stub = pass-through for now, see [§7](#7-security--privacy)). Local extract + redact are the only local steps.
3. **Cloud Run extractor** — redacted *text* in; Gemini returns JSON with `is_sfsu_transcript` and the passed courses (D6).
   - `is_sfsu_transcript = false` ⇒ **we stop**: 422, nothing saved. Only `true` proceeds (D13).
4. Normalize codes against `courses` ([§2](#2-data-model)) → save to `user_courses`. A code not in `courses` (e.g. a since-retired SFSU number) is **kept and flagged**, never silently dropped.

The PDF is never stored. Because Gemini makes the SFSU call, a non-SFSU transcript's *redacted* text does reach Google before being rejected, which is one more reason the redaction guard in [§7](#7-security--privacy) matters. Transfer credit and scanned PDFs are out of scope by design (D13).

### 1.3 Flow B — pathway
`POST /pathways {program, interest}`:
1. **Parse interest** — Gemini → structured intent (topics, keywords). Cached ([§6](#6-redis-caching)).
2. **Baseline (deterministic)** — common roadmap, passed courses marked done. No specialization ⇒ return this and stop.
3. **Candidates** — Gemini calls MCP tools ([§4](#4-mcp-tools--pathway-engine)) to fetch interest-relevant courses from pgvector, restricted to what each swappable slot allows.
4. **Gemini edits** — proposes swaps of *non-core* slots as structured edit ops, each with a reason (the AI step).
5. **Validator (deterministic, authoritative)** — see [§2.3](#23-unit-rules-validator-d12). Checks (a) prerequisites satisfied by earlier terms / passed courses ([§2.1](#21-prerequisites-use-the-scraped-code-lists-add-light-logic-revised)), (b) only swappable slots touched and replacements come from the slot's pool ([§2.2](#22-core-vs-swappable-slots-revised-d10)), (c) **minimum units**: degree total, major units, and each requirement section's units. Invalid edits are rejected with the violation fed back to Gemini (max 2 retries). Still failing ⇒ keep the valid edits, baseline for the rest.
6. **Result** — saved to the account, cached, returned with reasons.

> Principle (D5): Gemini **proposes**, the validator **decides**. A hallucinated or prerequisite-skipping edit can never reach the student.

Depends on: [§2](#2-data-model), [§4](#4-mcp-tools--pathway-engine). Used by: [§5](#5-api-surface).

---

## 2. Data model
Status: **Proposed**

Source of truth is **Postgres**. pgvector holds course embeddings only, in the same DB so one query can combine similarity with relational filters (D2).
Data comes from the scraper output (`scraping/sfsu_output/*.json`) via [§3](#3-ingestion-pipeline).

| Table | Key columns | Notes |
|---|---|---|
| `users` | id, email (unique), password_hash | email must end `@sfsu.edu` (text match, D7) |
| `programs` | id, slug, title, college, department, degree_type, level, concentration, total_units | ~378 rows |
| `courses` | id, code (unique), subject, number, title, units_min/max, description, prereq_text, **prereq_codes**, **prereq_groups**, **concurrent_ok**, **prereq_warnings**, **embedding** (vector) | ~4,995 rows; see [§2.1](#21-prerequisites-use-the-scraped-code-lists-add-light-logic-revised) |
| `requirement_sections` | id, program_id, heading, units, position, **kind** (`core`/`elective`/`ge`/`other`), notes | from the *Degree Requirements* tab |
| `requirement_items` | section_id, course_id?, raw_code, or_with_previous | allowed/required courses per section |
| `roadmaps` | id, program_id, name, total_units_required, major_units, source_url | ~364 rows |
| `roadmap_terms` | id, roadmap_id, position, label | "First Semester"… |
| `roadmap_slots` | id, term_id, position, course_id?, title, tags, units, footnotes, **swappable** (bool), **pool_section_id**? | the unit the pathway engine edits |
| `user_courses` | user_id, course_id?, raw_code, grade?, term?, flagged | from [Flow A](#12-flow-a--transcript-upload) |
| `pathways` | id, user_id, program_id, roadmap_id, interest_raw, intent (jsonb), result (jsonb), created_at | saved results |

### 2.1 Prerequisites: use the scraped code lists, add light logic (revised)
The scraper already extracts `prerequisite_courses` (clean course codes) and keeps the raw text for display. Checked against the data:

- **1,725** courses have a code list (avg 2 codes); the other ~2,650 with prerequisite text have only non-course conditions ("permission of instructor", "graduate standing"). Only **10** lists miss a code visible in the text, so the lists are reliable.
- What the flat list **lacks** is AND/OR: **844** lists have 2+ codes, and in most of those the text contains "or"/"/" (some are non-course "or"s such as "Psychology or School Psychology", but real ones exist, e.g. `ENGR 281* or ENGR 282*`).
- **`*` after a code means "may be taken concurrently"** (572 courses), which decides whether a course in the *same* term counts.

So per course we store:

| Column | Source | Meaning |
|---|---|---|
| `prereq_text` | scraper | display only |
| `prereq_codes` | scraper `prerequisite_courses` | the courses involved |
| `prereq_groups` | ingestion ([§3](#3-ingestion-pipeline)) | list of AND-ed groups; each group is OR-ed codes. Default = every code its own group (strict AND) |
| `concurrent_ok` | `*` in text | codes that may be taken in the same term |
| `prereq_warnings` | ingestion | non-course conditions, shown but never blocking |

**Strict by default.** If the ingestion clause parser cannot confidently split an "or", the codes stay AND-ed. That can only over-reject a valid swap, never let a skipped prerequisite through. No LLM is needed for this; a Gemini-assisted parse of the ambiguous remainder is an optional later improvement.

### 2.2 Core vs swappable slots (revised, D10)
Gemini may edit **two kinds of slot**; everything else is fixed.

| Slot kind | Roadmap text looks like | May be replaced by | Pool source |
|---|---|---|---|
| `major_elective` | "Major Elective (15 Units Total) - Take Three" (+ footnote to *Degree Requirements*) | only courses **listed in the program's Electives section** | `requirement_items` of the linked `requirement_section` |
| `free_elective` | "University Elective", "SF State Studies or University Elective", "Complementary Studies or … Elective" | **any course** (D11: fully free, no SF State Studies check) | whole `courses` table |
| not swappable | tagged `Major Core` / `Upper-Division Core` / `Concentration` / `Graduate Core` / `Credential`, "Select One (Major Core)", GE areas, US & California Government, etc. | — | — |

**One slot = one course.** A roadmap row like "Major Elective (15 Units Total) - Take Three" (9 units) is stored once with `seats = 3`, and is **split into three single-course slots** (`id-1`, `id-2`, `id-3`, 3 units each) when the baseline is built. A slot holds one course, or two for a lecture+lab pair.

Set at ingestion ([§3](#3-ingestion-pipeline)) by rule from slot text, tags and footnotes. Stored as `roadmap_slots.slot_kind`, `swappable` and `pool_section_id`.

Data facts that shape this (scraped data, all programs):
- Roadmap items with no course code: 7,297 of 12,757. Of those, about 3,250 look like elective/choice slots and about 3,070 are GE.
- Only **129 of 378** programs have an "Electives" section that lists courses. For other programs we cannot derive a major-elective pool, so those slots stay **non-swappable** (baseline shown, with a note) until ingestion heuristics widen.
- Elective sections also carry **prose rules** ("at least 12 units must be CSC", "any 600-level CSC except CSC 601…"). v1 enforces the **listed pool**; prose rules are stored as `notes` and surfaced to Gemini and as validator **warnings**, not blocks.

### 2.3 Unit rules (validator, D12)
The validator also guarantees the edited pathway still meets the **minimum units** for the degree. What the data provides:

| Rule | Data | Availability |
|---|---|---|
| Degree total ≥ required total (e.g. 120) | `roadmaps.total_units_required` ("120 Total Units Required") | 166 of 364 roadmaps |
| Major units ≥ required (e.g. 74) | `roadmaps.major_units`; same figure is the requirements heading "(B.S.) – 74 units" | 151 roadmaps; 213 of 378 programs |
| Each requirement section ≥ its units (e.g. Electives 15) | `requirement_sections.units` | 1,161 of 1,828 sections |

- **Fallback when a total is unknown:** the edited pathway may not total fewer units than the **baseline roadmap**. Same for a section with no stated units: swapped slots must keep that section's baseline unit total. So the check never silently disappears.
- **Variable-unit courses** (635 roadmap slots have ranges) count at `units_min`, the conservative choice.
- Units from **passed courses** count toward totals; each passed course counts once.
- Failures are **blocks** (fed back to Gemini). Missing data is a **warning** shown to the student.
- A "74 units" heading is *major* units, not the degree total. Do not conflate them.
- **Implementation (stronger than the table above):** an edit is rejected unless the replacement's `units_min` is **at least the slot's units**. Slot units never decrease, so the degree total, major units and every section total can never fall below the baseline. The validator then only *warns* when even the baseline is under a stated minimum.

Depends on: [§3](#3-ingestion-pipeline). Used by: [§4](#4-mcp-tools--pathway-engine) (reads), [§1.3](#13-flow-b--pathway).

---

## 3. Ingestion pipeline
Status: **Proposed**

One idempotent command, `python -m gatorway.ingest`, reads the scraper output (`SCRAPE_DIR`, default `scraping/sfsu_output/`) and fills the [§2](#2-data-model) tables. Re-running updates in place; it never duplicates. Schema comes from SQLAlchemy models with `create_all` (no migration tool for the hackathon).

| Step | What it does | Feeds |
|---|---|---|
| 1. Courses | upsert `courses` by `code` (title, units, description, `prereq_text`, `prereq_codes`) | [§2](#2-data-model) |
| 2. Programs | upsert `programs`, `requirement_sections` + `requirement_items`, `roadmaps` → `roadmap_terms` → `roadmap_slots`; resolve every course code to a `courses` row | [§2](#2-data-model) |
| 3. Prerequisite grouping | build `prereq_groups` and `concurrent_ok` (rules below) | [§2.1](#21-prerequisites-use-the-scraped-code-lists-add-light-logic-revised) |
| 4. Slot classification | set `slot_kind`, `swappable`, `pool_section_id` (rules below) | [§2.2](#22-core-vs-swappable-slots-revised-d10) |
| 5. Embeddings | Gemini embedding model, text = `code + title + description`, stored as `vector(768)` with an HNSW cosine index; skipped for a course whose text hash is unchanged | [§4](#4-mcp-tools--pathway-engine) `search_courses` |
| 6. Report | counts per table, requirement/roadmap codes missing from `courses`, slots by kind, programs without an elective pool | sanity check |

**Prerequisite grouping (deterministic, step 3).** Split the text on `;` into clauses. Within a clause, codes joined by "or" or "/" form one OR-group; everything else is its own group (AND). If a clause is unclear, each code stays its own group (strict, D9). A `*` after a code sets `concurrent_ok`. Anything with no course code goes to `prereq_warnings`.

**Slot classification (step 4).** Course-bearing slots tagged core (`Major Core`, `Upper-Division Core`, `Concentration`, `Graduate Core`, `Credential`, …) are not swappable. Generic slots:
- title contains "University Elective" ⇒ `free_elective`, pool = all courses (D11);
- title contains "Major Elective" **and** the program has an Electives section with course rows ⇒ `major_elective`, pool = that section (D10);
- GE areas, "US and California Government", "Select One (Major Core)", everything else ⇒ not swappable.

**Done means:** table row counts equal the JSON counts (4,995 courses; 378 programs; 364 roadmaps), every roadmap and requirement course code resolves or appears in the report, and step 5 yields an embedding for every course with a description (4,986).

Depends on: scraper output ([scraping/](scraping/)), [§2](#2-data-model). Used by: [§4](#4-mcp-tools--pathway-engine).

## 4. MCP tools & pathway engine
Status: **Proposed**

Two layers, so the rules live in plain testable code and not in the LLM:

1. **Engine** (`gatorway.engine`, pure Python over the [§2](#2-data-model) tables): `build_baseline`, `validate`, `apply_edits`. No Gemini, no network.
2. **MCP server** (FastMCP, :8001): thin tool wrappers over the engine and pgvector. This is what Gemini calls.

### 4.1 Data shapes
- **Pathway** — terms → slots. Each slot: `slot_id` (a string), `codes` (empty when open), `title`, `units`, `slot_kind` ([§2.2](#22-core-vs-swappable-slots-revised-d10)), `swappable`, `status` (`passed` / `planned` / `replaced`).
- **Edit** — `{slot_id, new_course_code, reason}`: one course into one single-course slot. Gemini's only way to change a pathway. A "Take Three" row is three slots, so three edits.
- **ValidationResult** — `violations` (blocks) and `warnings`, each tied to a `slot_id` and a rule.

### 4.2 MCP tools
Gemini never sees the user or the full pathway JSON. The orchestrator creates a **pathway session** (baseline + passed courses, held in Redis, [§6](#6-redis-caching)) and gives Gemini only a `session_id`.

| Tool | Does | Used by |
|---|---|---|
| `list_programs(query)` / `get_program(program_id)` | find and describe programs | API / Gemini |
| `get_roadmaps(program_id)` | roadmaps for a program; the default (common) one is flagged | API |
| `get_requirements(program_id)` | degree-requirement sections and unit minimums | Gemini |
| `get_baseline(session_id)` | the deterministic pathway, swappable slots marked, passed courses marked | Gemini |
| `search_courses(session_id, slot_id, query, limit)` | pgvector similarity, **restricted to the slot's pool** ([§2.2](#22-core-vs-swappable-slots-revised-d10)) and excluding courses already passed or planned | Gemini |
| `validate_edits(session_id, edits)` | run the validator on proposed edits; returns violations and warnings | Gemini |

`build_baseline` and `open_session` (stores the baseline and passed courses, returns the `session_id`) are also tools, but they are called by the orchestrator, not by Gemini, and are not on the `GEMINI_TOOLS` allowlist.

### 4.3 Validator rules (authoritative, deterministic)
Every edit, and then the whole edited pathway, must pass:
1. **Slot rule** — the slot is `swappable`, and the new course is in its pool ([§2.2](#22-core-vs-swappable-slots-revised-d10)).
2. **No duplicates** — not already passed, and not elsewhere in the pathway.
3. **Prerequisites** — for **every course in the pathway, including later ones**: each `prereq_groups` group is met by a passed course or one in an **earlier** term; same term only for a `concurrent_ok` code ([§2.1](#21-prerequisites-use-the-scraped-code-lists-add-light-logic-revised)). Checking the whole pathway catches a swap that removes a course a later one depended on.
4. **Units** — degree total, major units, section units ([§2.3](#23-unit-rules-validator-d12)).
5. **Warnings only** — non-course prerequisites, elective prose rules.
- **Only newly introduced violations block an edit.** The university's own roadmap can already break a rule (e.g. a prerequisite scheduled late); that is not the edit's fault and must not block every swap.
- **Search level filter:** for an `undergraduate` program `search_courses` excludes courses numbered 700 and above (graduate).
- **Baseline passed-course placement:** a roadmap slot whose courses were all passed is marked `passed`; an open `major_elective` slot is filled from the elective pool with a passed course; free electives and GE slots are **never** auto-filled (a passed course there cannot be attributed safely). Passed courses placed nowhere are returned as `unplaced_passed`.
- **"Passed" means credit earned:** A–D-, CR, P. F, W, NC, I, IP do not count.
Out of scope: whether a course is actually offered in a given term (not in the data).

### 4.4 Orchestration (`POST /pathways`, [Flow B](#13-flow-b--pathway))
1. Gemini parses the interest → `{specialization, topics, keywords}` (cached). **No specialization ⇒ return the baseline; Gemini is never used again.**
2. Orchestrator calls `build_baseline`, stores the session.
3. Gemini runs a tool loop (`get_baseline`, `search_courses`, `validate_edits`) and ends with a structured list of **edits with reasons**.
4. Orchestrator re-validates with the engine itself, regardless of what Gemini did. Violations go back to Gemini, **at most 2 retries**.
5. Still-invalid edits are dropped one by one; valid ones are kept; the rest stays baseline. The result lists applied edits with reasons and any dropped edits with the rule that blocked them.
6. Save to `pathways`, cache, return.

Failure handling: Gemini error or timeout ⇒ return the baseline with a note; empty search ⇒ no edits.

### 4.5 Testing
Engine unit tests on fixtures from real data (e.g. the CS B.S.): a swap that skips a prerequisite is rejected; so is one that removes a later course's prerequisite, and one that drops units below 120. Tools tested through the FastMCP in-memory client. Gemini is mocked in tests; one manual end-to-end run uses the real model.

### 4.6 Adding tools later (D15)
Tools are meant to be added freely, with no edits to the server or orchestrator:
- **One tool = one module** in `gatorway/mcp/tools/` that exposes a function and registers itself. The server loads every module in that folder at startup, so adding a file adds a tool.
- Tools stay thin: validate arguments, call the engine or the DB, return JSON. Logic goes in the engine ([§4](#4-mcp-tools--pathway-engine)), so a tool never needs to be rewritten when rules change.
- **Which tools Gemini may call** is a config allowlist (`GEMINI_TOOLS`), separate from which tools exist. Orchestrator-only tools such as `build_baseline` stay off the list.
- Tool descriptions and argument schemas are the contract Gemini reads, so each tool documents itself with a docstring and typed arguments.

Depends on: [§2](#2-data-model), [§3](#3-ingestion-pipeline). Used by: [§5](#5-api-surface), [Flow B](#13-flow-b--pathway).

## 5. API surface
Status: **Proposed**

FastAPI, JSON, OpenAPI docs at `/docs`. Auth is a bearer JWT. Errors share one shape: `{"error": {"code", "message", "details"}}`.

| Endpoint | Auth | Purpose |
|---|---|---|
| `POST /auth/signup` `{email, password}` | — | creates the account; email must be `@sfsu.edu` or a subdomain such as `@mail.sfsu.edu` (text match, case-insensitive; never `evilsfsu.edu` or `sfsu.edu.evil.com`, D7), else 422 |
| `POST /auth/login` | — | returns an access token |
| `GET /auth/me` | yes | current user |
| `POST /transcripts` (multipart PDF) | yes | [Flow A](#12-flow-a--transcript-upload). 201 with passed courses (+ flagged codes); 422 if unreadable or not an SFSU transcript |
| `GET /me/courses` | yes | the saved passed-course list |
| `DELETE /me/courses` | yes | delete the saved course list (privacy) |
| `GET /programs?query=&level=` | — | search programs (degree type, level, concentration) |
| `GET /programs/{id}` | — | program details |
| `GET /programs/{id}/roadmaps` | — | roadmaps; the common one is flagged |
| `GET /programs/{id}/requirements` | — | degree-requirement sections |
| `POST /pathways` `{program_id, roadmap_id?, interest?, fresh?, avoid?}` | yes | [Flow B](#13-flow-b--pathway). No `interest` ⇒ baseline only. Returns the pathway ([§4.1](#41-data-shapes)): terms and slots, applied edits with reasons, dropped edits with the blocking rule, warnings, plus `id` and the raw `interest`. `fresh: true` skips the cache (the UI's Refresh); `avoid` (≤20 codes) tells the model which earlier picks to steer away from |
| `POST /pathways/baseline` `{program_id, roadmap_id?}` | yes | the deterministic roadmap only: no Gemini, not saved or cached. The UI draws this while personalising runs |
| `GET /pathways`, `GET /pathways/{id}` | yes | saved pathways; the list items carry `program_title`, `roadmap_name`, `interest`, `swaps`, `created_at` |
| `GET /pathways/{id}/slots/{slot_id}/options?query=&limit=` | yes | other courses that could take one swappable slot (the same search the model uses, so they already respect the pool, level, units and prerequisites). A blank `query` falls back to the saved interest, then the slot title |
| `POST /pathways/{id}/swap` `{slot_id, new_course_code}` | yes | the student's own pick for one slot, validated by the same rules as the model's edits; a slot swapped before can be swapped again. 422 `swap_rejected` with the reasons if refused; the saved pathway is updated in place |
| `GET /courses?codes=A,B` | — | display details (description, prerequisites, attributes) for up to 60 course codes |
| `GET /health` | — | liveness: Postgres, Redis |

- `POST /pathways` is **synchronous** for the hackathon (a Gemini loop, a few seconds). If it proves slow, it becomes a job with polling later.
- `POST /pathways` needs saved courses; with none, it still works and treats the student as having passed nothing.
- **Rate limits** (Redis, [§6](#6-redis-caching)) on `/auth/login`, `/transcripts` and `/pathways`.

Depends on: [§1.2](#12-flow-a--transcript-upload), [§1.3](#13-flow-b--pathway), [§4](#4-mcp-tools--pathway-engine). Used by: the frontend ([§8](#8-frontend)).

## 6. Redis caching
Status: **Proposed** (D8)

All keys are prefixed `gw:`. Values are JSON unless noted. Two version tokens go into keys so stale entries are never served and never need manual clearing: `data_version` (set by each ingest run, [§3](#3-ingestion-pipeline)) and `engine_version` (a constant bumped when engine or validator rules change, [§4](#4-mcp-tools--pathway-engine)).

| Key | Value | TTL | Why |
|---|---|---|---|
| `gw:session:{session_id}` | pathway session: program, roadmap, baseline, passed codes ([§4.2](#42-mcp-tools)) | 30 min | Gemini sees only the id; tools read the session |
| `gw:intent:{sha256(normalized interest + model)}` | parsed intent `{specialization, topics, keywords}` | 7 days | same interest text ⇒ no second Gemini call |
| `gw:embq:{sha256(text + embed_model)}` | query embedding (768 floats) | 7 days | no re-embedding the same search string |
| `gw:pathway:{sha256(program_id, roadmap_id, sorted passed codes, intent hash, data_version, engine_version)}` | final pathway result ([§4.1](#41-data-shapes)) | 24 hours | identical request ⇒ instant answer, no Gemini or vector calls |
| `gw:lock:pathway:{same hash}` | `1` (`SET NX`) | 60 s | two identical requests at once do the work once; the second waits for the cache |
| `gw:rl:{endpoint}:{user_id or ip}:{window}` | counter (`INCR` + `EXPIRE`) | window length | rate limiting |

- **Normalized interest** = lowercased, trimmed, whitespace collapsed.
- **Rate limits** (per [§5](#5-api-surface)): `/auth/login` 10/min per IP; `/transcripts` 5/hour per user; `/pathways` 20/hour per user (each can cost Gemini calls).
- **Not cached:** course embeddings (stored once in pgvector, [§3](#3-ingestion-pipeline)) and anything holding user identity. Pathway cache keys hash only course content, so the cached value holds no personal data.
- **If Redis is down:** caches are skipped and rate limiting fails open with a warning. Pathways with a specialization need sessions, so they return the baseline with a note; `/health` reports Redis ([§5](#5-api-surface)).

Used by: [Flow B](#13-flow-b--pathway), [§4.4](#44-orchestration-post-pathways-flow-b), [§5](#5-api-surface).

## 7. Security & privacy
Status: **Proposed** (hackathon level: demo transcripts only)

- Passwords hashed with argon2; email domain check is a plain text match (D7). JWT secret and all keys come from `.env` (gitignored).
- The PDF is never stored; only extracted course codes are ([Flow A](#12-flow-a--transcript-upload)). `DELETE /me/courses` removes them.
- **`Redactor` port**: stub pass-through for now, real local code plugged in later. Redacted text is the only thing sent to Google.
- **Stub warning:** with the stub, nothing is redacted. Fine for demo transcripts; a config flag (`REDACTION_ENABLED`) logs a loud startup warning when it's off, and real student transcripts should not be used until a real redactor is registered.
- The Cloud Run extractor stores nothing and logs no transcript text ([§1.1](#11-what-runs)). The API calls it with a shared secret in an `X-Api-Key` header (hackathon-level auth; Cloud Run is deployed publicly reachable, the key keeps strangers out).

## 8. Frontend
Status: **Approved** (built)

`frontend/` is a Next.js 16 (App Router) single page with Tailwind 4 and `motion` for animation, talking to the API with a bearer token kept in `localStorage`. Light theme, SF State purple and gold used as soft tints; serif display type; large radii; no hard blocks.

**Flow:** sign in / create account → transcript → program (and roadmap variant) → interest (skippable) → roadmap. Past roadmaps open from a history sheet; clicking a course card opens a sheet with its description, prerequisites, why it was picked, and other options to swap in. "New interest" re-runs with new text; "Refresh picks" re-runs with `fresh` and `avoid`.

**Streaming boxes** are a client-side staggered reveal, not server streaming: the page first calls `POST /pathways/baseline` and fills the term rows card by card, then saves the real result with `POST /pathways`; when it arrives the AI picks morph in one after another with a sparkle badge. Saved roadmaps skip the show. Long steps (reading the transcript, Gemini personalising) show only a series of rotating words that fit the moment — never a progress bar, and no privacy line.

**Swaps** reuse the validator (`swap_slot`, `reopen_slot`): a student's pick is held to the same slot rule, pool, level, duplicate, unit and prerequisite checks as the model's.

---

## Decision log

| # | Decision | Why | See |
|---|---|---|---|
| D1 | FastAPI backend; FastMCP for tools | requested | [§1.1](#11-what-runs) |
| D2 | **pgvector in Postgres**, not a separate vector DB | ~5k vectors; one query mixes similarity + relational filters; one fewer service | [§2](#2-data-model) |
| D3 | Everything local; only Postgres + Redis in Docker; API and MCP run as plain processes | hackathon | [§1.1](#11-what-runs) |
| D4 | Cloud Run extractor is the Google service (hackathon requirement) | requirement | [§1.1](#11-what-runs) |
| D5 | Deterministic baseline → Gemini edits → deterministic validator; validator is authoritative | correctness of prerequisites/units can't depend on an LLM | [§1.3](#13-flow-b--pathway) |
| D6 | Extractor takes **redacted text**, returns JSON; Gemini only, no Document AI. Scanned PDFs deferred | simplest for now | [§1.2](#12-flow-a--transcript-upload) |
| D7 | Accounts: email + password, `sfsu.edu` (or subdomain, e.g. `mail.sfsu.edu`) text match, no verification; store passed courses + saved pathways, never the PDF | requested | [§2](#2-data-model), [§7](#7-security--privacy) |
| D8 | Redis for sessions, intent parses, query embeddings, built pathways, locks, rate limits (keys and TTLs in §6) | avoid redundant Gemini/vector calls | [§6](#6-redis-caching) |
| D9 | Prerequisites use the scraped `prerequisite_courses` lists plus a deterministic AND/OR grouping (strict AND when unsure) and `*` = concurrent OK; non-course conditions are warnings | lists are reliable; only AND/OR is missing; strict can over-reject but never under-check | [§2.1](#21-prerequisites-use-the-scraped-code-lists-add-light-logic-revised) |
| D10 | Swappable slots: **major electives** (pool = the program's Electives list in Degree Requirements) and **free electives** (any course). Core, GE and everything else are fixed. Programs without a parseable elective list keep those slots fixed | requested; pool lists exist for 129/378 programs | [§2.2](#22-core-vs-swappable-slots-revised-d10) |
| D11 | "SF State Studies or University Elective" slots are fully free-swappable; no SF State Studies attribute check | requested (Q4) | [§2.2](#22-core-vs-swappable-slots-revised-d10) |
| D12 | Validator enforces minimum units: degree total, major units, per-section units; baseline-total fallback when unstated; `units_min` for ranges | requested; unit data is partial | [§2.3](#23-unit-rules-validator-d12) |
| D13 | **SFSU transcripts only.** Gemini (the extractor) decides `is_sfsu_transcript`; `false` ⇒ stop. No extractable text (scanned) ⇒ rejected. No transfer-equivalency mapping, no OCR. Locally we only extract and redact | requested | [§1.2](#12-flow-a--transcript-upload) |
| D14 | Gemini sees only a `session_id` (baseline + passed courses live in Redis); it proposes edits via tools, and the orchestrator re-validates with the engine regardless | keeps user data and rules out of the LLM; validator stays authoritative | [§4.2](#42-mcp-tools), [§4.4](#44-orchestration-post-pathways-flow-b) |
| D15 | MCP tools are one-module-each and auto-registered; Gemini's callable tools are a config allowlist, so tools can be added freely | requested | [§4.6](#46-adding-tools-later-d15) |
| D16 | Streaming boxes are a client-side staggered reveal over a baseline preview endpoint; long steps show only rotating words, never progress bars | the full answer arrives at once; requested look | [§8](#8-frontend) |
| D17 | Student swaps use the same validator as the model, and an already-swapped slot can be swapped again (known limit: a replacement's units become the slot's minimum for later swaps) | one source of truth for the rules | [§5](#5-api-surface), [§8](#8-frontend) |
| D18 | GE rows are swappable (slot kind `ge`): any course labelled for that GE area (current or older label; lower- vs upper-division by the row's `UD`) can fill one, validated like any swap. The slot keeps its original wording in `label` so it can be swapped again. **Gemini only edits `major_elective` and `free_elective` slots**; GE is the student's own choice | requested; keeps the model's work small and the student in control of GE | [§5](#5-api-surface), [§8](#8-frontend) |
| D19 | **Real local redaction** before any transcript text reaches Gemini: GLiNER `nvidia/gliner-PII` (from Hugging Face) runs in the API process on the text pdfplumber extracted. Labels: person, student id, SSN, email, phone, address, date of birth. Names get a second pass at threshold 0.3 (other labels 0.5; lower flagged grades as IDs); spans are clipped to a line; course codes, grades, terms and the institution name are never redacted. **Fail closed**: if the model cannot load or run, the upload is refused (503 `redaction_unavailable`) and nothing is sent. `REDACTOR=stub` turns it off for tests and demos | requested; real student data must not reach an LLM unredacted | [§7](#7-security--privacy), [§1.2](#12-flow-a--transcript-upload) |

## Open questions

| # | Question | Affects |
|---|---|---|
| — | *None open.* Resolved so far: Q1 → D10, Q4 → D11; Q2/Q3 closed by D13. |
| Q1 | ~~Which slots may Gemini swap?~~ **Resolved → D10** | [§2.2](#22-core-vs-swappable-slots-revised-d10) |
| Q4 | ~~SF State Studies or University Elective~~ **Resolved → D11** | [§2.2](#22-core-vs-swappable-slots-revised-d10) |
