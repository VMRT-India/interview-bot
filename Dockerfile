FROM python:3.14-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY main.py config.py alembic.ini entrypoint.sh ./
COPY api/ ./api/
COPY db/ ./db/
COPY models/ ./models/
COPY prompts/ ./prompts/
COPY services/ ./services/

RUN chmod +x entrypoint.sh

# entrypoint.sh expands $PORT itself then `exec`s uvicorn, so signals (e.g.
# Render's SIGTERM on deploy/restart) reach the app directly instead of a shell.
CMD ["./entrypoint.sh"]
