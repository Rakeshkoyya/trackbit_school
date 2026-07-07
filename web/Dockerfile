# syntax=docker/dockerfile:1
#
# TrackBit Web — production image (Next.js standalone output).
# Build context: the repo root (trackbit_web/). Built by Dokploy from this Dockerfile.
#
# NEXT_PUBLIC_* is normally inlined at BUILD time, which makes a Docker image
# hard to repoint at a different backend. To keep this image runtime-
# configurable, we build with a sentinel value and swap it for the real URL on
# container start (see docker-entrypoint.sh). So in your platform you just set:
#     NEXT_PUBLIC_API_BASE_URL=https://api.your-domain.com/api/v1   (or http://IP:PORT/api/v1)
# as a normal ENVIRONMENT variable and restart — no rebuild needed.
# (Passing it as a --build-arg still works and takes precedence.)

# ---- deps: install node_modules ----
# Use `npm install`, not `npm ci`. package-lock.json is generated on Windows,
# which omits Linux-only optional native deps (Tailwind v4 `oxide`'s
# wasm32-wasi @emnapi subtree, sharp's linux builds). On alpine, strict `npm ci`
# aborts on those ("Missing @emnapi/* from lock file"); `npm install` reconciles
# the lock and installs the full tree. (node:24 bundles npm 11.)
FROM node:24-alpine AS deps
RUN apk add --no-cache libc6-compat
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm install --no-audit --no-fund

# ---- builder: compile the Next.js app ----
FROM node:24-alpine AS builder
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY . .

# Default to a sentinel so the value can be injected at runtime by the
# entrypoint. Pass a real --build-arg here to bake it in instead.
ARG NEXT_PUBLIC_API_BASE_URL=APP_RUNTIME_API_BASE_URL
ENV NEXT_PUBLIC_API_BASE_URL=$NEXT_PUBLIC_API_BASE_URL
ENV NEXT_TELEMETRY_DISABLED=1

RUN npm run build

# ---- runner: minimal runtime image ----
FROM node:24-alpine AS runner
WORKDIR /app
ENV NODE_ENV=production \
    NEXT_TELEMETRY_DISABLED=1 \
    PORT=3000 \
    HOSTNAME=0.0.0.0

# Run as a non-root user.
RUN addgroup --system --gid 1001 nodejs \
    && adduser --system --uid 1001 nextjs

# Static assets + the standalone server (which bundles its own minimal node_modules).
COPY --from=builder /app/public ./public
COPY --from=builder --chown=nextjs:nodejs /app/.next/standalone ./
COPY --from=builder --chown=nextjs:nodejs /app/.next/static ./.next/static

# Runtime API-URL injector (swaps the build sentinel for the real value).
COPY docker-entrypoint.sh /usr/local/bin/docker-entrypoint.sh
RUN chmod +x /usr/local/bin/docker-entrypoint.sh

USER nextjs
EXPOSE 3000

ENTRYPOINT ["/usr/local/bin/docker-entrypoint.sh"]
CMD ["node", "server.js"]
