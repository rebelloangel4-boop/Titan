FROM python:3.12-slim-bookworm
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 TITAN_DB=/data/titan.db TITAN_ARTIFACT_DIR=/data/artifacts
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg ca-certificates && rm -rf /var/lib/apt/lists/* \
    && useradd --uid 10001 --create-home titan && mkdir -p /data && chown titan:titan /data
WORKDIR /app
COPY --chown=root:root titan /app/titan
USER 10001:10001
EXPOSE 8787
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8787/healthz',timeout=3)"
CMD ["python","-m","titan.server","--host","0.0.0.0","--port","8787"]
