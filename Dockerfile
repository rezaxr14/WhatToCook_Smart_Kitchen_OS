# Pinned by digest (the multi-arch index, so amd64 and arm64 both resolve): the tag says what it is, the digest makes the build
# repeatable. Dependabot (docker ecosystem) moves the digest; a fixable OS finding in this base fails the scan until it does.
FROM python:3.11-slim@sha256:cce12316475d7d56d605f76e1d811d0dc4e7227f2d4afd29951521264f504ff8

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Run as an unprivileged user (uid 10001). Kubernetes pins the same uid and
# sets fsGroup so mounted volumes stay writable.
RUN useradd --system --uid 10001 --user-group --no-create-home --shell /usr/sbin/nologin app \
    && chown app:app /app

# Dependencies first for layer caching: code changes don't reinstall them.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Application code
COPY --chown=app:app . .

RUN chmod +x /app/entrypoint.sh

USER 10001

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/api/health/', timeout=5).status==200 else 1)"

ENTRYPOINT ["/app/entrypoint.sh"]
CMD ["web"]
