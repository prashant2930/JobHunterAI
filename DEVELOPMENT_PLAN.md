# JobHunter AI — Development Plan (V1)

This document maps out the structured development phases for building **JobHunter AI** as a local-first application. Each phase includes a clear goal, feature set, dependency list, expected output, and testing requirements to ensure clean progress.

---

## Phase 0: Project Foundation 🟢 (Completed)
- **Goal**: Initialize the project directory structure, prepare the Python backend environment, verify frontend-backend communication, and setup SQLite database.
- **Features**:
  - Configure the local directory layout (FastAPI + React + SQLite).
  - Setup Python virtual environment (`.venv`) and install essential requirements (`fastapi`, `uvicorn`, `sqlmodel`, `pydantic-settings`).
  - Create backend router framework with basic endpoints (`/api/health`).
  - Set up SQLite database initialization on server startup.
- **Expected Output**: Running FastAPI server at `http://localhost:8000` responding to health checks, database status connected, and Vite frontend running at `http://localhost:3000`.
- **Verification**: `/api/health` unit tests and CORS checks.

---

## Phase 1: Resume Intelligence 🟢 (Completed)
- **Goal**: Local resume file extraction, structured profile parsing using Gemini, and user review editing.
- **Features**:
  - Implement `/api/profile/resume` file upload route.
  - Implement local text extraction service (`pypdf` + `docx2txt`) for PDFs and DOCXs.
  - Set up provider-neutral `BaseLLMClient` interface and implementation (`GeminiClient`).
  - Call Gemini Structured Output mode using `CandidateProfileSchema` responses.
  - Expose API routes to save authoritative candidate profiles.
- **Expected Output**: User uploads resume, system parses details, displays bento-grid editor, and saves results in SQLite.
- **Verification**: `backend/tests/test_resume.py` unit tests (PDF/DOCX mocks, schema constraints, upload route testing).

---

## Phase 2: Job Discovery & Aggregation 🟢 (Completed)
- **Goal**: Collect job listings from public sources, normalize titles/companies/skills, filter duplicates conservatively, and populate SQLite.
- **Features**:
  - Define `BaseJobSource` scraper interface.
  - Implement `AdzunaSource` (key-based public queries) and `RemoteOKSource` (open remote job feed, no key required).
  - Write `JobNormalizationService` (company legal suffix strips, location mappings, and skill aliases).
  - Implement `JobDeduplicationService` (Level 1: strict ID/URL check, Level 2: normalized identity check with supporting description token overlap checks).
  - Implement `/api/jobs/search` aggregator route, `/api/jobs` lists, and details drawer in frontend.
- **Expected Output**: Search query aggregates jobs across sources, normalizes details, and saves unique records in SQLite.
- **Verification**: `backend/tests/test_jobs.py` (normalizers, conservative deduplication, title false-positives, repeated ingestion updates, and jobs API).

---

## Phase 3: Suitability & Match Engine 🟢 (Completed)
- **Goal**: Evaluate stored jobs against the active candidate profile using a hybrid 100-point scoring algorithm and generate explanations using Gemini.
- **Features**:
  - Implement **100-point Deterministic scoring splits** (Skills: 35, Experience: 20, Role Title: 15, Location: 15, Education: 10, Qualification Compliance: 5).
  - Implement **Strict Remote and Location checking** (distinguishes strict Remote mismatches, preferred Remote, and unspecified preferences).
  - Implement **Severe experience mismatch cap** (caps overall score at 40/100 for severe experience gaps, logging details in concerns).
  - Implement **Selective Gemini triggers** (invoked only on ambiguity signals: fuzzy titles, related education fields, or text experience statements; skips Gemini for clear-cut matches/mismatches).
  - Add privacy-centric prompting (strips email, phone, and complete names from LLM queries).
  - Setup `/api/matches/job/{job_id}`, `/api/matches/search` (batch matching with concurrency semaphore limit of 5), and ranked retrieval endpoints.
  - Implement composite uniqueness index (`candidate_profile_id` + `job_id`) to update records instead of duplicating.
  - Create robust, fully offline fallback to deterministic results on Gemini timeout, API failure, or invalid response formats.
- **Expected Output**: Dashboard highlights suitabilities, details missing required vs preferred skills, and outlines concerns.
- **Verification**: `backend/tests/test_match.py` unit tests verifying strong matches, missing required penalties, missing preferred deductions, experience caps, location scenarios, aliases, ambiguity triggers, and API timeout fallbacks.


---

## Phase 4: UI Refinement, Weight Tuner & Polish 🔴 (Pending)
- **Goal**: Build configuration controls, adjust matching weights, and refine frontend user experience.
- **Features**:
  - Add **Configuration Panel**: Edit API keys and customize weights (slidables for skills, experience, locations).
  - Setup unified single-command runner script (e.g. `npm run dev:all` or helper script).
  - Conduct E2E E2E testing (Resume upload -> Job search -> Match rating check).
- **Expected Output**: Polished V1 monolithic system ready for local installation.

---

## Future Agentic Evolution (V2 / V3)
Once the monolithic V1 system is stable and correct, it can transition into an autonomous multi-agent pipeline:
- **Resume Optimizer Agent**: Customizes profile details for high-matching roles.
- **Autonomous Scraper Agent**: Crawls target companies' career portals respecting `robots.txt`.
- **Application Tracker Agent**: Drafts application emails and cover letters.
