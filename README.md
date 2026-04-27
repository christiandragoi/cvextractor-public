# CV Extractor — Docker-Ready FastAPI App

FastAPI backend with a single-page HTML/JS frontend. Upload, extract, and manage candidate CVs (PDF/DOCX/DOC). Works in **demo mode** without any API key, or with **OpenAI** for LLM-powered extraction.

---

## What You Get

- **FastAPI** async API with SQLite database
- **Static HTML/JS frontend** served at `/` — no build step needed
- **File upload + extraction** — drag-and-drop or click, supports PDF/DOCX/DOC
- **Candidate management** — list, view, filter, delete
- **Dashboard** — pipeline stats (total, review, completed, failed)
- **Demo extraction** — regex/heuristic extraction works without any API key
- **OpenAI extraction** — plug in `OPENAI_API_KEY` for LLM-powered parsing

---

## Project Structure

```
cv-extractor/
├── main.py                          # FastAPI entry point
├── requirements.txt                 # Python dependencies
├── Dockerfile                       # Docker image build
├── docker-compose.yml               # Docker Compose orchestration
├── .env.example                     # Environment variables template
├── .dockerignore                    # Files excluded from Docker build
├── nginx/
│   └── cv-extractor.conf            # Nginx reverse-proxy sample
├── app/
│   ├── __init__.py
│   ├── config.py                    # App settings (storage paths, CORS)
│   ├── database.py                  # SQLAlchemy async engine + session
│   ├── errors.py                    # Custom exceptions
│   ├── models/
│   │   └── candidate.py             # SQLAlchemy Candidate model
│   ├── schemas/
│   │   └── candidate.py             # Pydantic response schemas
│   ├── routers/
│   │   ├── candidates.py            # Upload, extract, CRUD
│   │   ├── extraction.py            # Intake process, download
│   │   ├── templates.py             # Template stub
│   │   ├── settings.py              # Settings / provider stub
│   │   ├── config_router.py         # Health check
│   │   ├── identcheck.py            # IdentCheck stub
│   │   ├── processing.py            # Processing stub
│   │   └── review.py                # Review stub
│   ├── services/
│   │   ├── candidate_service.py     # Candidate creation + file save
│   │   └── template_population_service.py  # DOCX/PDF text extraction
│   └── clients/
│       └── ai_client.py             # OpenAI + demo fallback
└── static/
    └── index.html                   # Complete SPA frontend
```

---

## Quick Start — Local Docker Test

```bash
# 1. Clone or copy the project folder
cd cv-extractor

# 2. Copy environment template
cp .env.example .env

# 3. Build and start the container
docker compose up --build -d

# 4. Check it's running
curl http://localhost:8000/api/v1/health

# 5. Open the UI
http://localhost:8000
```

### Stop / Restart

```bash
# Stop
docker compose down

# Restart with new code (rebuilds image)
docker compose up --build -d

# View logs
docker compose logs -f app

# Full reset (removes DB + uploads)
docker compose down -v
```

---

## Environment Variables

Copy `.env.example` to `.env` and set values:

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `DATABASE_URL` | No | `sqlite+aiosqlite:///app/data/cv_extractor.db` | SQLite DB path inside container |
| `STORAGE_ROOT` | No | `/app/storage` | Upload/output directory inside container |
| `OPENAI_API_KEY` | No | — | Enables OpenAI extraction instead of demo mode |
| `OPENAI_BASE_URL` | No | `https://api.openai.com/v1` | OpenAI-compatible endpoint |
| `OPENAI_MODEL` | No | `gpt-4o-mini` | Model to use |
| `CORS_ORIGINS` | No | `*` | Comma-separated allowed origins |

---

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/` | Web UI (static HTML) |
| `GET` | `/api/v1/health` | Health check |
| `POST` | `/api/v1/candidates/upload` | Upload a CV (creates candidate) |
| `POST` | `/api/v1/candidates/extract` | Upload + extract in one call |
| `GET` | `/api/v1/candidates` | List all candidates |
| `GET` | `/api/v1/candidates/{id}` | Get single candidate |
| `DELETE` | `/api/v1/candidates/{id}` | Delete candidate |
| `DELETE` | `/api/v1/candidates` | Delete all candidates |
| `POST` | `/api/intake/process` | Full intake workflow |
| `POST` | `/api/process` | Legacy extraction endpoint |
| `GET` | `/api/download/{id}` | Download generated DOCX (if available) |

---

## Nginx Reverse Proxy (VPS)

Place `nginx/cv-extractor.conf` inside `/etc/nginx/sites-available/` on your Hostinger VPS, adjust the `server_name`, then:

```bash
sudo ln -s /etc/nginx/sites-available/cv-extractor.conf /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

For HTTPS, use Certbot:

```bash
sudo apt install certbot python3-certbot-nginx
sudo certbot --nginx -d your-domain.com
```

---

## VPS Deployment — Exact Commands

On your Hostinger VPS (after uploading the project folder via SCP/Git):

```bash
cd cv-extractor
cp .env.example .env
# (optional) nano .env and add OPENAI_API_KEY

docker compose up --build -d
```

That's it. The app binds to `127.0.0.1:8000` inside the VPS and is exposed to Nginx only. Data and uploads persist in `./data` and `./storage` on the host.

---

## Notes

- **No Streamlit** anywhere — this is a proper FastAPI + HTML/JS web app.
- **No migration commands** — tables are auto-created on first startup.
- **No build step** for the frontend — `static/index.html` is served as-is.
- The `docker-compose.yml` binds to `127.0.0.1:8000` so the app is not exposed directly to the internet; Nginx handles external traffic.
