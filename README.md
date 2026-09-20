# EcoMind AI — Sustainability Assistant

**1M1B AI for Sustainability Virtual Internship** (in collaboration with IBM SkillsBuild & AICTE)

An AI-powered sustainability assistant built around a Retrieval-Augmented
Generation (RAG) pipeline, plus a carbon footprint estimator that reuses the
same retrieval engine to generate a personalized tip.

## 1. Project description

| | |
|---|---|
| **Title** | EcoMind AI — Sustainability Assistant |
| **Primary SDG** | SDG 13 — Climate Action |
| **Secondary SDGs** | SDG 7 — Affordable and Clean Energy · SDG 12 — Responsible Consumption and Production |
| **Problem statement** | People who want to act more sustainably are faced with scattered, inconsistent advice and no quick way to see how their own habits compare to an actual footprint. |
| **AI solution** | A retrieval-augmented assistant answers free-text sustainability questions by matching them (TF-IDF + cosine similarity) against a curated 48-entry knowledge base spanning energy, water, waste, transport, food, biodiversity, climate action and city policy, then composing a grounded answer that cites which topics it drew from. A footprint estimator computes an annual CO2e estimate from a few habit inputs and calls the same retrieval engine to surface a targeted tip for the user's biggest contributing category. |
| **Target users** | Students, households, and community groups who want practical, trustworthy sustainability guidance without wading through inconsistent sources. |

## 2. Architecture — one frontend, two engines

`ecomind_ai.html` (shipped alongside this backend) is now a **real,
integrated** frontend rather than two disconnected copies of the same logic:

- On load, it pings `GET /health` on this backend. If it responds, the
  sidebar shows **"Connected to backend"** and every question/footprint
  calculation is sent here (`POST /chat`, `POST /footprint`) and answered by
  the real `scikit-learn` TF-IDF + cosine-similarity pipeline below.
- If the backend isn't running — closed, on a different port, or the page
  was opened as a plain file with no server at all — the sidebar shows
  **"Offline mode"** and the page falls back to an equivalent TF-IDF engine
  built into the HTML/JS itself, so the demo never breaks.
- If a request to a previously-reachable backend fails mid-session (server
  stopped, network drop), the badge updates immediately and subsequent
  requests use the offline engine automatically — no reload needed.

This means you can demo it two ways from the *same* file: with the backend
running (shows off the real ML pipeline), or completely offline (zero
install, for a quick live demo).

## 3. Running the backend

```bash
# 1. Create a virtual environment (recommended)
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Run the server
uvicorn app:app --reload

# 4. Open the interactive API docs
# http://127.0.0.1:8000/docs

# 5. Open ecomind_ai.html in a browser — it will detect the backend
#    automatically and show "Connected to backend"
```

If `uvicorn app:app --reload` won't launch (e.g. corporate Device Guard
blocking the `uvicorn.exe` shim on Windows), run it as a module instead,
which just executes `python.exe`:

```bash
python -m uvicorn app:app --reload
```

Try the API from the command line:

```bash
curl -X POST http://127.0.0.1:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"query": "how can I lower my energy bill"}'

curl -X POST http://127.0.0.1:8000/footprint \
  -H "Content-Type: application/json" \
  -d '{"car_km_week": 120, "elec_kwh_month": 250, "diet": "average", "short_flights": 1, "long_flights": 0}'
```

Or run the included smoke test, which exercises both endpoints directly
against the Python module (no server needed):

```bash
python test_rag.py
```

## 4. Configuration

Every setting has a sensible default and can be overridden with an
environment variable — see `config.py` for the full list:

| Variable | Default | Purpose |
|---|---|---|
| `ECOMIND_HOST` | `127.0.0.1` | Bind host |
| `ECOMIND_PORT` | `8000` | Bind port |
| `ECOMIND_LOG_LEVEL` | `INFO` | `DEBUG` also logs each query's text and match scores |
| `ECOMIND_CORS_ORIGINS` | `*` | Comma-separated list to restrict which origins can call the API |
| `ECOMIND_KB_PATH` | `data/kb.json` | Swap in a different knowledge base without touching code |
| `ECOMIND_RETRIEVAL_K` | `3` | Max knowledge-base entries returned per answer |
| `ECOMIND_MIN_SCORE` | `0.05` | Similarity threshold below which a match is discarded |
| `ECOMIND_MAX_QUERY_LEN` | `500` | Longest query the API will accept |

## 5. Logging & error handling

- Every request logs one structured line — method, path, status code, and
  duration — via a request-logging middleware in `app.py`.
- Startup fails fast (with a clear log message) if `data/kb.json` is
  missing, malformed, or has entries with unknown categories, instead of
  starting a server that would 500 on every request.
- Invalid input (empty query, negative footprint values, an unrecognized
  diet) is rejected with `422` and a specific message via Pydantic
  validators on `ChatRequest`/`FootprintRequest`; anything that still slips
  through as a `ValueError` inside `rag.py` is caught and turned into a
  clean `400`. Unexpected errors return a generic `500` and are logged with
  a full traceback server-side — never leaked to the client.

## 6. Tests

```bash
pip install -r requirements.txt   # includes pytest + httpx
pytest                            # run from ecomind_backend/
pytest -v                         # verbose, one line per test
```

- `tests/test_rag.py` — unit tests for the retrieval engine and footprint
  calculator: knowledge-base loading/validation, retrieval ranking and
  thresholds, input validation, footprint math.
- `tests/test_api.py` — integration tests for the FastAPI layer using
  `TestClient`: routing, status codes, validation errors, CORS headers.

`pytest.ini` sets `pythonpath = .` so the tests can import `app`/`rag`
directly without installing the project as a package.

## 7. Project structure

```
ecomind_backend/
├── app.py                FastAPI app: /chat, /footprint, /topics, /health
├── rag.py                RAG engine: TF-IDF retrieval + answer composition
├── config.py             Centralized, env-overridable settings
├── logging_config.py     Structured console logging setup
├── data/kb.json           48-entry curated sustainability knowledge base
├── test_rag.py            Standalone smoke test — no server, no pytest needed
├── tests/
│   ├── test_rag.py         Unit tests (pytest)
│   └── test_api.py         API integration tests (pytest)
├── pytest.ini
├── requirements.txt
└── README.md
```

## 8. Responsible AI considerations

- **Fairness** — the knowledge base favors low-cost, broadly applicable
  actions over ones that assume home ownership or high income; footprint
  factors use global averages rather than one country's assumptions.
- **Transparency** — every chat response returns `matched_entries`, showing
  exactly which knowledge-base items informed the answer; the frontend
  surfaces this as "Retrieved from" tags and always shows whether the
  answer came from the backend or the offline fallback.
- **Ethics** — the assistant only composes answers from its curated
  knowledge base; it does not fabricate statistics or claim certainty it
  doesn't have, and says so explicitly when nothing matches well.
- **Privacy** — no user query or footprint input is stored anywhere. At the
  default `INFO` log level, only the request path/status/timing is logged
  — the query text itself is only logged if you explicitly turn on
  `ECOMIND_LOG_LEVEL=DEBUG` for local debugging.

## 9. Expected impact

A user who consistently uses the assistant to identify and act on their
highest-impact category (as flagged by the footprint estimator) addresses
the largest, most controllable share of a typical household's emissions —
transport and home energy — rather than spreading limited effort across
lower-impact changes.

## 10. Limitations

Footprint figures are simplified planning estimates built from public
average emission factors, not certified carbon accounting, and should not
be used for regulatory or offset-purchase decisions. The assistant can only
answer from its ~48-entry knowledge base.
