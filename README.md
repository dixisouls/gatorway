# GatorWay

**Your degree roadmap, tuned to what you love. Gemini picks the electives; rules check every prerequisite.**

Built for **SF Hacks x GDG AI Hackathon** · for San Francisco State students

---

## The problem

Every SF State student plans eight semesters from a one-size-fits-all PDF roadmap that ignores what they've already taken and what they actually care about. Picking electives means digging through ~5,000 courses and checking prerequisites by hand, and a wrong guess can cost a semester.

## Our solution

Upload a transcript (or just explore), pick a degree, and say what excites you: *"AI and machine learning"*. GatorWay shows the official roadmap instantly, then **Gemini fills your electives with courses that fit you**, each with a reason. A rules engine checks every one against prerequisites, units and level, so **the AI can suggest, but it can never break your plan**.

## Why it's more than a chatbot

| Idea | What we did |
|---|---|
| **AI proposes, rules decide** | Gemini searches the catalog through a tool server (FastMCP) and proposes swaps. A deterministic validator checks each one for allowed courses, level, duplicates, units and prerequisites across the *whole* pathway. Anything invalid is dropped. |
| **Real data, not guesses** | We scraped the SFSU bulletin: 4,995 courses, 378 programs, 364 official roadmaps. The baseline roadmap is built by rules; the AI never invents a course. |
| **Meaning-based search** | Courses are embedded locally (bge-base) in Postgres + pgvector, so "AI" finds *Hardware for Machine Learning* and *Deep Learning*. |
| **Privacy first** | Transcript text is redacted **on-device** with GLiNER (`nvidia/gliner-PII`) before Gemini sees it, and it **fails closed**: if redaction can't run, nothing is sent. |
| **Not a chat app** | A designed planner: streaming roadmap, golden AI picks with reasons, expandable course cards, choose-one groups, GE tracking, saved history. |

## Google technology

- **Gemini (Vertex AI):** understands the student's interest, reads the transcript into structured courses, and proposes the elective picks through tool calls.
- **Firebase Authentication:** sign-up and sign-in, with ID tokens verified on every API call (SFSU email addresses only).

## Architecture

```text
 Browser (Next.js)  ──Firebase ID token──▶  FastAPI
      │                                       │  ├─ pdfplumber ▶ GLiNER redaction ▶ extractor (Gemini)  → your courses
      │                                       │  ├─ baseline roadmap (rules)
      │                                       │  └─ Gemini ◀── tools ──▶ MCP server ─▶ Postgres + pgvector
      └────────── streaming reveal ◀──────────┘                              ▲
                                  validator re-checks every pick ────────────┘
```

**Stack:** Next.js · React · TypeScript · Tailwind · Motion · FastAPI · FastMCP · SQLAlchemy · Postgres + pgvector · Redis · sentence-transformers · GLiNER · pdfplumber.

**Quality:** 257 backend tests and 148 frontend tests, plus checks run against the real services (Gemini, Firebase, the redaction model).

## Honest limits

Transfer and GE credit on a transcript isn't matched to SFSU courses yet (students mark GE rows themselves). "Choose one" picks and completed GE rows are remembered in the browser only. Redaction is a model, so it's best-effort. This is a hackathon build, run locally rather than deployed.

---

Developer docs: [`docs/SETUP.md`](docs/SETUP.md) (running it locally) · [`ARCHITECTURE.md`](ARCHITECTURE.md) (design and decisions) · [`DEVLOG.md`](DEVLOG.md) (what we built, and why)
