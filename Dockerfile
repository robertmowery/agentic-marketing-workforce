# Part 7: the image Cloud Run builds and runs.
FROM python:3.13-slim

ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
WORKDIR /app

COPY deploy/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY workforce ./workforce
COPY deploy ./deploy

# Do not run as root.
RUN useradd --create-home agent
USER agent

# Cloud Run tells the container which port to listen on.
CMD ["sh", "-c", "exec uvicorn deploy.main:app --host 0.0.0.0 --port ${PORT:-8080}"]
