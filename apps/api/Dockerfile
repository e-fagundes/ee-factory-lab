FROM python:3.12-slim

WORKDIR /app
COPY apps/api/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY apps/api/app ./app
COPY config ./config
COPY templates ./templates

ENV PYTHONPATH=/app \
    REPO_ROOT=/app
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
