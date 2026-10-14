# ── Production Image ─────────────────────────────────────────
FROM python:3.11-slim

# Prevent .pyc files and enable unbuffered stdout/stderr
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Install dependencies first (cached layer — only rebuilds if requirements.txt changes)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy only the application code (frontend is served by Nginx, not this container)
COPY alembic.ini .
COPY alembic/ alembic/
COPY app/ app/

# Port Uvicorn will listen on inside the container
EXPOSE 8000

# Run Alembic migrations first, then start the FastAPI server
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000"]
