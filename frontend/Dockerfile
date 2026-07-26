FROM node:22-alpine AS builder
WORKDIR /app
ARG NEXT_PUBLIC_API_BASE_URL=/api
ENV NEXT_PUBLIC_API_BASE_URL=${NEXT_PUBLIC_API_BASE_URL}
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend ./
RUN npm run build

FROM node:22-alpine AS runner
WORKDIR /app
ENV NODE_ENV=production \
    HOSTNAME=0.0.0.0 \
    PORT=3000
RUN addgroup -S -g 10001 tuneai \
    && adduser -S -u 10001 -G tuneai tuneai
COPY --from=builder --chown=tuneai:tuneai /app/.next/standalone ./
COPY --from=builder --chown=tuneai:tuneai /app/.next/static ./.next/static
COPY --from=builder --chown=tuneai:tuneai /app/public ./public
EXPOSE 3000
USER tuneai
CMD ["node", "server.js"]
