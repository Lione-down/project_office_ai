FROM node:22.22.2-alpine AS build

WORKDIR /app
ENV PPT_RENDERER_BUILD_OUT_DIR=/tmp/ppt-renderer-dist
COPY package.json package-lock.json ./
RUN npm ci
COPY tsconfig.json tsconfig.build.json vitest.config.ts ./
COPY scripts ./scripts
COPY src ./src
COPY tests ./tests
RUN npm run build && cp -R /tmp/ppt-renderer-dist /app/dist

FROM node:22.22.2-alpine AS runtime

ENV NODE_ENV=production
WORKDIR /app
COPY --from=build --chown=10001:10001 /app/package.json /app/package-lock.json ./
RUN npm ci --omit=dev
COPY --from=build --chown=10001:10001 /tmp/ppt-renderer-dist ./dist
USER 10001:10001
CMD ["node", "dist/server.js"]
