# ⚡ API Pulse — High-Performance API & Uptime Monitoring Engine

[![FastAPI](https://img.shields.io/badge/FastAPI-0.115.0-009688?style=flat-square&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![Python](https://img.shields.io/badge/Python-3.11+-3776AB?style=flat-square&logo=python&logoColor=white)](https://www.python.org/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-15-4169E1?style=flat-square&logo=postgresql&logoColor=white)](https://www.postgresql.org/)
[![Docker](https://img.shields.io/badge/Docker-Ready-2496ED?style=flat-square&logo=docker&logoColor=white)](https://www.docker.com/)
[![License](https://img.shields.io/badge/License-MIT-blue.svg?style=flat-square)](LICENSE)

**API Pulse** is a modern, distributed API and uptime monitoring engine built with **FastAPI**, **PostgreSQL**, **APScheduler**, and **Nginx**. It provides real-time health checks, custom payload/header verification with Fernet symmetric encryption, JSON response assertions, multi-channel instant notifications (Slack, Discord, Email, SMS), and public status pages.

---

## ✨ Key Features

- ⏱️ **Scheduled Automated Health Checks**: Asynchronous background jobs powered by **APScheduler** and **HTTPX** running configurable interval checks (from 1 minute to hours).
- 🔐 **Encrypted Custom Headers & Tokens**: Sensitive headers (API keys, Bearer tokens, basic auth) are symmetrically encrypted using **Fernet** before persistence to the database.
- 📦 **Payload & Method Flexibility**: Full support for `GET`, `POST`, `PUT`, `PATCH`, and `DELETE` requests with custom JSON request bodies.
- 🎯 **Advanced Response Assertions**: Validate status codes, response time thresholds, and inspect JSON paths with custom conditions (e.g. `data.status == "active"`).
- 🚨 **Multi-Channel Alerting**: Instant incident alerts and recovery notifications via:
  - **Slack** (Incoming Webhooks)
  - **Discord** (Webhooks)
  - **Email** (SMTP / SSL / TLS via `aiosmtplib`)
  - **SMS** (Twilio integration)
- 📊 **Detailed Latency & Check History**: Tracks response time metrics, HTTP status codes, error traces, and assertion validation logs.
- 🌐 **Public Status Page**: Dedicated status page endpoints (`/status`) for user-facing uptime transparency.
- 🛡️ **JWT Multi-Tenant Authentication**: Secure user registration, password hashing with `bcrypt`, and stateless JWT access tokens.
- 🐳 **Production-Ready Docker Stack**: Single-command deployment orchestrating Nginx reverse proxy, FastAPI backend, and PostgreSQL with database health checks.

---

## 🏗️ Architecture

```
                      ┌─────────────────────────────────────────┐
                      │             Clients / Browser           │
                      └────────────────────┬────────────────────┘
                                           │
                                     Port 80 (HTTP)
                                           ▼
                      ┌─────────────────────────────────────────┐
                      │              Nginx Proxy                │
                      │  ├─ Serves Frontend Dashboard (/ui)     │
                      │  └─ Proxies API Requests (/api/*)       │
                      └────────────────────┬────────────────────┘
                                           │
                                    Port 8000
                                           ▼
                      ┌─────────────────────────────────────────┐
                      │          FastAPI Backend Engine         │
                      │  ├─ Auth & User Management (JWT)        │
                      │  ├─ Monitor CRUD & Assertion Engine     │
                      │  └─ APScheduler (In-Memory Jobs)        │
                      └─────────────┬─────────────┬─────────────┘
                                    │             │
                    AsyncPG Queries │             │ HTTPX Checks
                                    ▼             ▼
  ┌───────────────────────────────────┐    ┌──────────────────────────────────┐
  │         PostgreSQL Database       │    │     Target APIs & Webhooks       │
  │  ├─ Users & Encrypted Credentials │    │  ├─ Monitored Endpoints          │
  │  ├─ Monitors & Assertions         │    │  └─ Alerts: Slack, Discord,      │
  │  └─ Check Logs & Metrics          │    │            Email, Twilio SMS     │
  └───────────────────────────────────┘    └──────────────────────────────────┘
```

---

## 🛠️ Tech Stack

- **Backend Framework**: [FastAPI](https://fastapi.tiangolo.com/) (Python 3.11+)
- **Database & ORM**: [PostgreSQL](https://www.postgresql.org/) with [SQLAlchemy 2.0](https://www.sqlalchemy.org/) (AsyncIO) & [AsyncPG](https://github.com/MagicStack/asyncpg)
- **Migrations**: [Alembic](https://alembic.sqlalchemy.org/)
- **Job Scheduling**: [APScheduler](https://apscheduler.readthedocs.io/)
- **HTTP Client**: [HTTPX](https://www.python-httpx.org/) (Async HTTP client)
- **Security**: [Fernet Cryptography](https://cryptography.io/), [Python-Jose (JWT)](https://github.com/mpdavis/python-jose), [Bcrypt](https://pypi.org/project/bcrypt/)
- **Notifications**: [aiosmtplib](https://github.com/cole/aiosmtplib), [Twilio SDK](https://www.twilio.com/docs/libraries/python)
- **Web Server / Reverse Proxy**: [Nginx](https://nginx.org/)
- **Containerization**: [Docker](https://www.docker.com/) & [Docker Compose](https://docs.docker.com/compose/)

---

## 🚀 Quick Start with Docker (Recommended)

The easiest way to run API Pulse in production or local testing is using Docker Compose.

### 1. Clone the Repository
```bash
git clone https://github.com/<your-username>/api-pulse.git
cd api-pulse
```

### 2. Configure Environment Variables
Copy [.env.example](file:///.env.example) to `.env`:
```bash
cp .env.example .env
```

Generate your security keys:
```bash
# Generate SECRET_KEY for JWT
python -c "import secrets; print(secrets.token_hex(32))"

# Generate ENCRYPTION_KEY for stored API headers
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```
Fill in the generated values and database credentials inside `.env`.

### 3. Launch Services
```bash
docker compose up -d --build
```

### 4. Apply Database Migrations
Once containers are healthy, execute database migrations inside the backend container:
```bash
docker compose exec backend alembic upgrade head
```

### 5. Access the Platform
- **Frontend Dashboard**: [http://localhost](http://localhost)
- **Backend API & Swagger Docs**: [http://localhost:8000/docs](http://localhost:8000/docs)
- **Database Port**: `localhost:5433` (mapped externally to prevent conflicts with local Postgres)

---

## 💻 Local Development Setup (Without Docker)

### Prerequisites
- Python 3.11+
- Running PostgreSQL instance

### 1. Set Up Virtual Environment
```bash
python -m venv .venv

# Windows (PowerShell):
.venv\Scripts\Activate.ps1

# Linux / macOS:
source .venv/bin/activate
```

### 2. Install Dependencies
```bash
pip install -r requirements.txt
```

### 3. Configure `.env`
Ensure your local `DATABASE_URL` is set in `.env`:
```ini
DATABASE_URL=postgresql+asyncpg://postgres:your_password@localhost:5432/monitoring_db
SECRET_KEY=your_64_char_hex_key
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
ENCRYPTION_KEY=your_fernet_key
```

### 4. Run Migrations & Start Server
```bash
# Run migrations
alembic upgrade head

# Start FastAPI development server
uvicorn app.main:app --reload --port 8000
```
- Open Swagger documentation at [http://localhost:8000/docs](http://localhost:8000/docs)
- Open UI at [http://localhost:8000/ui](http://localhost:8000/ui)

---

## ⚙️ Environment Configuration

| Variable | Description | Example / Default |
| :--- | :--- | :--- |
| `DATABASE_URL` | Async PostgreSQL connection string | `postgresql+asyncpg://user:pass@localhost:5432/db` |
| `POSTGRES_USER` | Docker PostgreSQL user | `postgres` |
| `POSTGRES_PASSWORD` | Docker PostgreSQL password | `supersecretpassword` |
| `POSTGRES_DB` | PostgreSQL database name | `monitoring_db` |
| `SECRET_KEY` | Hex secret for JWT signing | `64-character hex string` |
| `ALGORITHM` | JWT signing algorithm | `HS256` |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | JWT expiration duration in minutes | `30` |
| `ENCRYPTION_KEY` | Symmetric Fernet key for headers | Base64 Fernet key |
| `SMTP_HOST` | SMTP server for email alerts | `smtp.gmail.com` |
| `SMTP_PORT` | SMTP port | `587` |
| `SMTP_USER` | SMTP username / sender | `alerts@example.com` |
| `SMTP_PASSWORD` | SMTP password / app password | `app_password` |
| `TWILIO_SID` | *(Optional)* Twilio Account SID | `ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx` |
| `TWILIO_TOKEN` | *(Optional)* Twilio Auth Token | `your_auth_token` |
| `TWILIO_PHONE` | *(Optional)* Twilio Sender Phone | `+1234567890` |

---

## 📖 API Documentation & Endpoints

FastAPI provides interactive API docs at `/docs` (Swagger UI) and `/redoc`.

### Core Routes:
| Method | Endpoint | Description | Auth Required |
| :--- | :--- | :--- | :--- |
| `POST` | `/users/register` | Register new user account | No |
| `POST` | `/users/token` | Authenticate & obtain JWT token | No |
| `GET` | `/monitors/` | List all monitors for active user | Yes |
| `POST` | `/monitors/` | Create a monitor with intervals & assertions | Yes |
| `GET` | `/monitors/{id}` | Retrieve monitor configuration | Yes |
| `PUT` | `/monitors/{id}` | Update monitor parameters | Yes |
| `DELETE`| `/monitors/{id}` | Soft-delete / remove monitor | Yes |
| `GET` | `/logs/{monitor_id}` | Retrieve check execution logs & response times | Yes |
| `POST` | `/alerts/channels` | Configure Slack/Discord/Email/SMS channels | Yes |
| `GET` | `/status/{monitor_id}`| Public endpoint for status badges / pages | No |

---

## 🧪 Database Migrations

This project uses [Alembic](https://alembic.sqlalchemy.org/) for schema versioning:

```bash
# Create a new migration revision after modifying models
alembic revision --autogenerate -m "describe_changes"

# Apply pending migrations
alembic upgrade head

# Roll back the last migration
alembic downgrade -1
```

---

## 📂 Project Structure

```text
MonitoringEngine/
├── alembic/                # Alembic migration scripts and env configuration
├── app/
│   ├── alerts/             # Alert channels (Slack, Discord, Email, SMS)
│   ├── core/               # App configuration, security, Fernet encryption
│   ├── logs/               # Execution logs, metrics, history router & models
│   ├── monitors/           # Monitor CRUD, scheduler, worker & assertion rules
│   ├── status/             # Public status page & badge endpoints
│   ├── users/              # Auth, JWT, user models & routers
│   ├── database.py         # Async SQLAlchemy engine & session factory
│   └── main.py             # FastAPI entrypoint, lifespan & router mounting
├── frontend/               # Dashboard, monitor manager, static HTML/CSS/JS
├── .env.example            # Sample environment variables
├── .gitignore              # Git ignore rules
├── Dockerfile              # Container definition for FastAPI backend
├── docker-compose.yml      # Orchestration for Nginx, Backend, and PostgreSQL
├── nginx.conf              # Nginx reverse proxy & static frontend routing
└── requirements.txt        # Python package dependencies
```

---

## 🤝 Contributing

Contributions, issues, and feature requests are welcome!
1. Fork the Project
2. Create your Feature Branch (`git checkout -b feature/AmazingFeature`)
3. Commit your Changes (`git commit -m 'feat: add some AmazingFeature'`)
4. Push to the Branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

---

## 📄 License

Distributed under the MIT License. See `LICENSE` for more information.
