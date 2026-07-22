FROM node:22.17.0-alpine

ENV NODE_ENV=development
WORKDIR /app

COPY --chown=10001:10001 package.json package-lock.json ./
RUN npm ci

COPY --chown=10001:10001 . .

USER 10001:10001

CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0"]
