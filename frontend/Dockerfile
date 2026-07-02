# Standalone frontend container: build the Vite SPA, serve it with nginx.
# Self-contained — no /api reverse proxy here (that's a later, optional gateway
# in front). The SPA's API base is baked at build time from VITE_API_BASE.

FROM node:20-alpine AS build
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
# Same-origin default; override to the backend origin for a split-origin deploy
# (e.g. --build-arg VITE_API_BASE=http://localhost:8000/api).
ARG VITE_API_BASE=/api
ENV VITE_API_BASE=$VITE_API_BASE
RUN npm run build

FROM nginx:alpine
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 80
