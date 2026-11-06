FROM python:3.12-slim

LABEL org.opencontainers.image.title="MovieBox API Pro"
LABEL org.opencontainers.image.description="Pure REST API wrapper for moviebox.ph — zero scraping"
LABEL org.opencontainers.image.authors="Faisal <https://github.com/faisaljs>"
LABEL org.opencontainers.image.source="https://github.com/faisaljs/Moviebox-API"
LABEL org.opencontainers.image.licenses="MIT"
LABEL org.opencontainers.image.url="https://github.com/faisaljs/Moviebox-API"

WORKDIR /app

RUN groupadd --system moviebox && useradd --system --gid moviebox --home-dir /app moviebox \
    && mkdir -p /app/data && chown moviebox:moviebox /app/data

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    MOVIEBOX_BIND_HOST=0.0.0.0

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY *.py ./
COPY routes/ ./routes/
COPY static/ ./static/

USER moviebox

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD python -c "import httpx,os,sys; r=httpx.get('http://localhost:8000/health/ready',auth=(os.environ['MOVIEBOX_AUTH_USER'],os.environ['MOVIEBOX_AUTH_PASSWORD']),timeout=3); sys.exit(0 if r.status_code==200 else 1)"

CMD ["python", "main.py"]
