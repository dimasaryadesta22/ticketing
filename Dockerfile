# syntax=docker/dockerfile:1
# Dockerfile multi-stage Tiketin
#   deps    : memasang dependency Python ke virtualenv /opt/venv
#   test    : menjalankan pytest; build GAGAL jika ada test yang gagal (quality gate)
#   runtime : image kecil untuk produksi, berjalan sebagai user non-root
ARG PYTHON_VERSION=3.12

# ---------- stage 1: dependency ----------
FROM python:${PYTHON_VERSION}-slim AS deps
ENV PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1
WORKDIR /app
COPY requirements.txt .
RUN python -m venv /opt/venv \
 && /opt/venv/bin/pip install -r requirements.txt
ENV PATH="/opt/venv/bin:$PATH"

# ---------- stage 2: test (dipakai Jenkins: docker build --target test) ----------
FROM deps AS test
COPY requirements-dev.txt .
RUN pip install -r requirements-dev.txt
COPY . .
RUN python -m pytest

# ---------- stage 3: runtime (image yang di-push ke Docker Hub) ----------
FROM python:${PYTHON_VERSION}-slim AS runtime
ARG APP_VERSION=dev
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH" \
    APP_VERSION=${APP_VERSION}
WORKDIR /app

RUN useradd --create-home --uid 10001 appuser
COPY --from=deps /opt/venv /opt/venv
COPY tiketin ./tiketin
COPY scripts ./scripts
COPY manage.py wsgi.py ./
COPY docker/entrypoint.sh /entrypoint.sh
# sed: buang CRLF jika file di-commit dari Windows
RUN sed -i 's/\r$//' /entrypoint.sh && chmod +x /entrypoint.sh

USER appuser
EXPOSE 8000
HEALTHCHECK --interval=10s --timeout=3s --start-period=20s --retries=5 \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://localhost:8000/health', timeout=3).status == 200 else 1)"

ENTRYPOINT ["/entrypoint.sh"]
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "--workers", "3", "--threads", "4", "--access-logfile", "-", "wsgi:app"]
