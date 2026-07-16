# XGSail OTA update server (ota-service/) — standalone, talks only to MinIO.
# Build from the repo root:  docker build -f ota-service/Dockerfile .
FROM node:20-slim AS build
WORKDIR /app
COPY ota-service/package.json ota-service/package-lock.json ./
RUN npm ci
COPY ota-service/ .
RUN npm run build

FROM node:20-slim
WORKDIR /app
COPY ota-service/package.json ota-service/package-lock.json ./
RUN npm ci --omit=dev
COPY --from=build /app/dist ./dist

ENV NODE_ENV=production

# Run as non-root (uid distinct from backend's 10001 to avoid any accidental
# collision across images sharing a host).
RUN useradd --create-home --uid 10002 otaservice \
    && chown -R otaservice:otaservice /app
USER otaservice

EXPOSE 8081
CMD ["node", "dist/server.js"]
