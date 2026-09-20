# Development worker image. Build and sandbox operation must be verified on your host.
FROM mcr.microsoft.com/playwright/python:v1.57.0-noble
WORKDIR /app
COPY pyproject.toml ./
COPY frameport ./frameport
COPY fixtures ./fixtures
COPY web ./web
RUN python -m pip install --no-cache-dir -e . && mkdir /data && chown pwuser:pwuser /data
ENV FRAMEPORT_DATA=/data
USER pwuser
EXPOSE 8040
HEALTHCHECK --interval=30s --timeout=3s CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8040/api/health', timeout=2)"
CMD ["python", "-m", "frameport.cli", "--host", "0.0.0.0", "--port", "8040"]
