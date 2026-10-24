# End-to-end tests driving the real UI (web + api containers) in Chromium.
FROM mcr.microsoft.com/playwright:v1.64.1-noble
WORKDIR /e2e
ENV HOME=/tmp
COPY package.json package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY . .
CMD ["npx", "playwright", "test"]
