FROM node:20-alpine

ENV APPUSER=appuser
ENV APPUID=1001
ENV APPGID=1000

RUN adduser \
    --home "/app" \
    --uid "$APPUID" \
    --disabled-password \
    "$APPUSER"

RUN apk add --no-cache curl

WORKDIR /app
USER appuser

COPY --chown=appuser:appuser package.json .
COPY --chown=appuser:appuser package-lock.json .

RUN npm ci --legacy-peer-deps
HEALTHCHECK CMD curl --fail http://localhost:8080/health || exit 1
COPY --chown=appuser:appuser . /app
RUN npm run build

ENTRYPOINT [ "node", "dist/main.js" ]
