# JobHunter AI 🚀

JobHunter AI is a local-first, AI-powered job discovery and matching application. It allows users to upload their resume, parses it, structures it into a candidate profile, fetches job postings from allowed public sources, normalizes them, deduplicates, and runs a hybrid deterministic/AI matching engine using Gemini to score and rank suitability.

---

## 🎨 Current Project Status: Phase 3 — Suitability & Match Engine

This repository is set up for **Phase 3 — Suitability & Match Engine**. The local file extraction, public job crawlers, normalized SQLite schemas, bento Candidate Review dashboard, and 100-point hybrid match calculation engine (incorporating strict remote checking, experience caps, selective Gemini triggers, and fallbacks) are fully functional.


---

## 🏗️ Architecture Summary

JobHunter AI is designed as a local-first **Modular Monolith**:
1. **Frontend (React + TS + Tailwind)**: Multi-state dashboard containing file upload zone, loading screens, and bento-grid Candidate Profile Review panel.
2. **Backend (FastAPI)**: Ingests documents, extracts text, calls Gemini API using response schemas, and stores relationships in SQLite.
3. **Database (SQLite)**: SQLite database running locally at `backend/jobhunter.db` initialized automatically on server launch.

---

## 📄 Candidate Profile Schema (Version 1.0)
The profile structure separates facts explicitly stated in the resume from user-provided preferences:
* **Factual Extraction (Resume-Derived):**
  * **Personal Information:** Name, Email, Phone, Location.
  * **Education:** List of Degree, Field of Study, Institution, Graduation Year.
  * **Skills:** Split into Programming Languages, Frameworks, Libraries, Databases, Cloud, Tools, and Other Skills.
  * **Experience:** Company, Role, Location, Dates, Description, and Technologies.
  * **Projects:** Name, Description, Technologies, and URL.
  * **Certifications:** List of strings.
  * **Additional Information:** Achievements, Languages, and Websites.
* **Metadata & Preferences (User-Provided Only):**
  * **Job Preferences:** Preferred Roles, Preferred Locations, Remote Preference, Experience Level.
  * **Flags:** `profile_source` (`"extracted"` or `"user_provided"`) and `preferences_source` (`"none"` or `"user_provided"`). 

*Gemini is strictly instructed to NOT infer preferences; they remain empty/null until manually entered by the user in the dashboard review panel.*

---

## 🛠️ Prerequisites
* **Node.js**: Version 18+
* **Python**: Version 3.10+

---

## 🚀 Setup & Installation

### 1. Backend Setup
Navigate to the root directory and set up a Python virtual environment:
```bash
# Create virtual environment
python -m venv backend/.venv

# Activate virtual environment (Windows Powershell)
backend/.venv/Scripts/Activate.ps1

# Activate virtual environment (macOS/Linux)
source backend/.venv/bin/activate

# Install requirements
pip install -r backend/requirements.txt
```

### 2. Frontend Setup
In the root directory, install npm packages:
```bash
npm install
```

### 3. Environment Configuration
Copy the sample environment file to create a local `.env` configuration:
```bash
cp .env.example .env
```
Open `.env` and configure your settings:
* `BACKEND_URL`: Target URL for the API server (default: `http://localhost:8000`).
* `DATABASE_URL`: Connection string for SQLite (default: `sqlite:///./jobhunter.db`).
* `GEMINI_API_KEY`: API Key for Google Gemini integrations.

---

## 🖥️ Running Locally

### Start the Backend
From the root directory, run:
```bash
# Make sure virtual environment is active
cd backend
uvicorn app.main:app --reload --port 8000
```
* **Backend API URL**: `http://localhost:8000`
* **Health Endpoint**: `http://localhost:8000/api/health`

### Start the Frontend
From the root directory in a separate terminal shell, run:
```bash
npm run dev
```
* **Frontend Web Dashboard URL**: `http://localhost:3000`

---

## 🧪 Testing

### Run Backend Tests
Ensure the backend virtual environment is active, then run:
```bash
cd backend
pytest
```
This executes 9 tests covering:
1. API Health check validation.
2. PDF text extraction (`pypdf` mock validation).
3. DOCX text extraction (`docx2txt` mock validation).
4. File type and empty document checks.
5. Pydantic Candidate Schema constraints.
6. Endpoint multipart upload tests using an offline `FakeLLMClient`.

*No automated tests depend on live Gemini API calls, allowing verification to pass entirely offline.*

---

## 🔒 Security & Privacy Considerations
1. **Local Text Extraction:** Resumes are parsed locally using `pypdf` and `docx2txt`. Raw binary files are never saved or sent to external services.
2. **Provider Isolation:** LLM integration depends on a `BaseLLMClient` interface. Changing providers (e.g. to a local Ollama model) does not affect resume extraction services.
3. **No Key Leakage:** Gemini API calls are strictly handled from the FastAPI backend. Secrets are never exposed to the browser.
4. **No Sensitive Logging:** We do not log resume content or personal identifying information.
