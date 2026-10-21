# ---------- Stage 1: build the SPA ----------
# --platform=$BUILDPLATFORM: the output is plain JS/CSS, identical for every architecture, so it is built once on the native
# builder (emulating Node under QEMU for arm64 would be many times slower) and only the nginx stage below is per-architecture.
FROM --platform=$BUILDPLATFORM node:24-alpine AS build

WORKDIR /app

ENV NODE_OPTIONS="--max-old-space-size=1024"

COPY package.json package-lock.json ./
RUN npm ci --prefer-offline

COPY . .
RUN npm run build

# ---------- Stage 2: serve with nginx ----------
FROM nginx:alpine@sha256:892bb2152464f0c5d8972593a5f5afaf8054552580b699d95f8ff4af08c2d33d AS serve

# The base is pinned by digest (the multi-arch index), so a rebuild cannot silently change it. Alpine still publishes security
# fixes (libexpat, libx11, ...) before nginx rebuilds its image: take them now.
# CI builds this stage with --no-cache-filter so a cached copy of this layer cannot hide a newer fix.
RUN apk upgrade --no-cache

RUN rm /etc/nginx/conf.d/default.conf
COPY nginx.conf /etc/nginx/conf.d/default.conf
# Shared header/CSP snippets included by nginx.conf (one add_header set per location).
COPY nginx/ /etc/nginx/snippets/

COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 80

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD wget -q -O /dev/null http://127.0.0.1/ || exit 1

CMD ["nginx", "-g", "daemon off;"]
