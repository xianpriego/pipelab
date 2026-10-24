# syntax=docker/dockerfile:1.7
#
# Pipelab web UI: built with Vite, served by nginx which also proxies the
# API and its websockets to the "api" service.

FROM node:22-alpine AS deps
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci --no-audit --no-fund

# Used by `docker compose run web-test npm test -- --run` (and lint/typecheck).
FROM deps AS test
COPY . .
CMD ["npm", "test", "--", "--run"]

FROM test AS build
RUN npm run build

FROM nginx:1.27-alpine AS web
# host:port of the API service and the DNS server used to resolve it
# (127.0.0.11 is Docker's embedded DNS on compose networks).
ENV PIPELAB_API=api:8000 \
    PIPELAB_RESOLVER=127.0.0.11
COPY docker/default.conf.template /etc/nginx/templates/default.conf.template
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 80
