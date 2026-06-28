# ── Build stage ──────────────────────────────────────────────────────────────
# Compile TypeScript and bundle the React SPA into static assets.
FROM node:20-alpine AS builder

WORKDIR /app

# Separate dependency install so this layer is cached until package-lock changes
COPY package*.json ./
RUN npm ci

COPY . .
RUN npm run build
# /app/dist is now a production-ready static bundle

# ── Serve stage ───────────────────────────────────────────────────────────────
# nginx proxies /api/* to the backend and serves everything else as the SPA.
FROM nginx:1.27-alpine

RUN rm /etc/nginx/conf.d/default.conf

COPY --from=builder /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 8501

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD wget -qO- http://localhost:8501/ || exit 1

CMD ["nginx", "-g", "daemon off;"]
