FROM node:24-bookworm-slim AS deps
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci

FROM deps AS build
COPY . .
ARG INSIGHTFORGE_API_ORIGIN=http://api:8111
ENV INSIGHTFORGE_API_ORIGIN=$INSIGHTFORGE_API_ORIGIN NEXT_TELEMETRY_DISABLED=1
RUN npm run build && npm prune --omit=dev

FROM node:24-bookworm-slim
WORKDIR /app
ENV NODE_ENV=production NEXT_TELEMETRY_DISABLED=1
COPY --from=build --chown=node:node /app ./
USER node
EXPOSE 3101
CMD ["npx", "next", "start", "--port", "3101", "--hostname", "0.0.0.0"]
