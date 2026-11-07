FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PORT=8000 \
    MOVIEBOX_BIND_HOST=0.0.0.0

WORKDIR /app

# Install deps first so the layer caches across source changes.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the app source. No data dir — the app is stateless.
COPY main.py config.py state.py providers.py upstream.py helpers.py env_loader.py api_dashboard.html ./
COPY routes/ ./routes/

# Non-root user. The app writes nothing to disk, so this is just hygiene.
RUN useradd --create-home --shell /usr/sbin/nologin --uid 10001 app \
    && chown -R app:app /app
USER app

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD python -c "import httpx,sys; sys.exit(0 if httpx.get('http://127.0.0.1:8000/health',timeout=3).status_code==200 else 1)"

CMD ["python", "main.py"]