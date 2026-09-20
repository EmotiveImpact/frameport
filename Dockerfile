FROM node:22-bookworm-slim AS studio
WORKDIR /build
COPY package.json package-lock.json ./
RUN npm ci --ignore-scripts
COPY web ./web
RUN npm run build

FROM mcr.microsoft.com/playwright/python:v1.57.0-noble
WORKDIR /app
COPY pyproject.toml ./
COPY frameport ./frameport
COPY fixtures ./fixtures
COPY web ./web
COPY --from=studio /build/web/dist ./web/dist
COPY deploy/start-worker.sh ./deploy/start-worker.sh
RUN python -m pip install --no-cache-dir -e . && mkdir -p /data && chown pwuser:pwuser /data && chmod +x deploy/start-worker.sh
ENV FRAMEPORT_DATA=/data
ENV PYTHONUNBUFFERED=1
EXPOSE 8040
HEALTHCHECK --interval=30s --timeout=5s CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8040/api/ready', timeout=4)"
# Start script initialises the volume then drops privileges to pwuser.
ENTRYPOINT ["/app/deploy/start-worker.sh"]
