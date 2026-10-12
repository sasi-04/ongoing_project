FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 CAREAI_ENV=production
WORKDIR /app
RUN useradd -m -u 10001 care
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY careai ./careai
COPY static ./static
COPY data/knowledge_seed.json data/literature.json ./data/
RUN mkdir -p /app/var && chown -R care /app
USER care
ENV CAREAI_DB=/app/var/careai.db
EXPOSE 8000
HEALTHCHECK CMD python -c "import urllib.request;urllib.request.urlopen('http://localhost:8000/health')" || exit 1
CMD ["uvicorn", "careai.api:app", "--host", "0.0.0.0", "--port", "8000"]
