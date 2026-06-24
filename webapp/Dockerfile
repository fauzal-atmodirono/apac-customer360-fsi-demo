# Multi-stage build for the Next.js PWA (Cloud Run target).
FROM node:20-slim AS deps
WORKDIR /app
COPY package.json package-lock.json* ./
RUN npm ci

FROM node:20-slim AS builder
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY . .
RUN npm run build

FROM node:20-slim AS runner
WORKDIR /app
ENV NODE_ENV=production
# Next.js "standalone" output bundles a minimal server.
COPY --from=builder /app/public ./public
COPY --from=builder /app/.next/standalone ./
COPY --from=builder /app/.next/static ./.next/static
EXPOSE 3000
ENV PORT=3000
# On Cloud Run, attach a runtime service account with BigQuery + the masked-SA
# token-creator grant; ADC is provided automatically. No keys needed.
CMD ["node", "server.js"]
