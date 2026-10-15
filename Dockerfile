FROM node:24-bookworm-slim AS web
WORKDIR /build
RUN npm install --global pnpm@12.8.1
COPY web/package.json web/pnpm-lock.yaml web/pnpm-workspace.yaml ./
RUN pnpm install --frozen-lockfile
COPY web/ ./
RUN npm run build

FROM python:3.12-slim-bookworm AS app
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=/app/backend \
    MYCUT_DATA_DIR=/data MYCUT_WEB_DIR=/app/web/dist HF_HOME=/models \
    HF_HUB_DISABLE_TELEMETRY=1
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg fonts-dejavu-core fonts-dejavu-extra \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --create-home --uid 1000 studio \
    && mkdir /data /models && chown studio:studio /data /models
COPY backend/requirements.txt ./backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt
COPY backend/mycut ./backend/mycut
COPY --from=web /build/dist ./web/dist
USER studio
EXPOSE 8321
CMD ["python", "-m", "uvicorn", "mycut.api:app", "--host", "0.0.0.0", "--port", "8321"]
