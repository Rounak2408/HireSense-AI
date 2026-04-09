# HireSense AI

AI-powered resume intelligence platform for recruiters and candidates.

HireSense AI is a production-style HR-tech application where:
- recruiters can ingest resumes, analyze fit against job descriptions, and make shortlist/hold/reject decisions
- candidates can run self-check analysis before applying
- public users can submit resumes through a shareable intake flow for HR pre-screening

---

## What This App Does

### Recruiter workflow
- Create or select a job context
- Upload one or many resumes (`.pdf` / `.docx`)
- Auto-parse candidate profile (skills, experience, education, projects)
- Score and rank candidates
- View analytics and insights in dashboard panels
- Save/track analysis history

### Candidate workflow
- Paste JD + upload resume
- Get match score, ATS-style diagnostics, gaps, and improvements
- Review project-level analysis and strengths/risks

### Public intake workflow (shareable)
- A non-logged-in user can submit:
  - name
  - email
  - role keywords
  - resume
- HR can review submissions from dashboard inbox
- Auto rule supported:
  - if keyword match `< 30%`, candidate is auto-marked as rejected with notification text

---

## Core Features

- Premium dark/light UI theme
- Recruiter dashboard and command center
- Resume intelligence page with:
  - match intelligence
  - ATS review
  - skills breakdown
  - project analysis
  - recommendation board
- History and archive support
- Public resume submission + HR keyword filtering
- PostgreSQL-backed persistence (SQLAlchemy ORM)

---

## Tech Stack

- **Backend/App:** Python, Streamlit
- **Database:** PostgreSQL, SQLAlchemy
- **NLP/Parsing:** spaCy, regex, pdfplumber, PyPDF2, python-docx
- **Data/Charts:** pandas, Plotly

---

## Prerequisites

- Python 3.10+ (recommended)
- PostgreSQL 14+ running locally or remotely
- A database (example: `hiresense_db`)

---

## Local Setup

1. Create and activate virtual environment

```powershell
python -m venv .venv
.\.venv\Scripts\activate
```

2. Install dependencies

```powershell
pip install -r requirements.txt
python -m spacy download en_core_web_sm
```

3. Configure environment

Create `.env` from `.env.example` and set:

```env
DATABASE_URL=postgresql://postgres:YOUR_PASSWORD@localhost:5432/hiresense_db
SECRET_KEY=replace-with-long-random-string
UPLOAD_DIR=uploads
MAX_UPLOAD_MB=25
APP_ENV=development
```

4. Run app

```powershell
streamlit run app.py
```

Default local URL: `http://localhost:8502` (or streamlit-assigned port).

---

## Database Notes

- Tables are auto-created on app start (`init_db` + `Base.metadata.create_all`).
- Includes recruiter, candidate, screening, upload, resume-analysis, and public-intake entities.
- If schema changes are added later, use migrations for production deployments.

---

## Key Folders

```text
app.py                    # Streamlit entrypoint and app shell
config/                   # Environment settings
database/                 # Models + DB session
services/                 # Parsing, matching, scoring, screening logic
ui/                       # Theme, reusable components, pages
scripts/                  # Utility/seed scripts
uploads/                  # Stored resume files
```

---

## Useful Developer Notes

- If UI looks stale after CSS changes, do a hard refresh (`Ctrl + F5`).
- If database connection fails, verify `.env` password and DB existence.
- For larger file uploads, tune Streamlit server upload settings.

---

## Security Reminder

This project is a demo/portfolio-grade implementation.  
Before production use, add:
- HTTPS everywhere
- secure secret management
- role-based access hardening
- request throttling/rate limiting
- audit logging and monitoring

---

## License

Use as portfolio/learning base.  
Add your preferred license before public/commercial distribution.
