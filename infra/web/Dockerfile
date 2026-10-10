FROM node:24.20.0-alpine AS base
RUN apk add --no-cache tzdata && corepack enable
ENV PNPM_HOME=/pnpm
ENV PATH=/pnpm:$PATH
ENV NEXT_TELEMETRY_DISABLED=1

FROM base AS packages
WORKDIR /app
COPY package.json pnpm-lock.yaml pnpm-workspace.yaml ./
COPY web/package.json web/package.json
COPY e2e/package.json e2e/package.json
COPY sdks/nodejs-client/package.json sdks/nodejs-client/package.json
COPY cli/package.json cli/package.json
COPY packages packages
RUN corepack install && pnpm install --frozen-lockfile --ignore-scripts
COPY .company-web/package.json .company-web/package-lock.json .company-web/
RUN npm ci --prefix .company-web --ignore-scripts --no-audit --no-fund

FROM packages AS builder
COPY . .
RUN NODE_OPTIONS=--max-old-space-size=4096 node .company-web/check-projects-types.mjs
RUN node .company-web/localize-literals.mjs web && node --test .company-web/rtl.spec.mjs .company-web/members.spec.mjs
WORKDIR /app/web
ENV NODE_OPTIONS=--max-old-space-size=4096
ENV pnpm_config_verify_deps_before_run=false
RUN mkdir -p public/fonts && cp ../.company-web/node_modules/@fontsource-variable/vazirmatn/files/vazirmatn-arabic-wght-normal.woff2 public/fonts/ && cp ../.company-web/node_modules/@fontsource-variable/vazirmatn/LICENSE public/fonts/vazirmatn-license.txt
RUN pnpm exec next build --webpack

FROM base AS production
ENV NODE_ENV=production
ENV DEPLOY_ENV=PRODUCTION
ENV CONSOLE_API_URL=http://127.0.0.1:5001
ENV APP_API_URL=http://127.0.0.1:5001
ENV MARKETPLACE_API_URL=https://marketplace.dify.ai
ENV MARKETPLACE_URL=https://marketplace.dify.ai
ENV PORT=3000
ENV TZ=UTC
RUN addgroup -S -g 1001 dify && adduser -S -u 1001 -G dify dify
WORKDIR /app
COPY --from=builder --chown=dify:dify /app/web/.next/standalone ./targets/next/
COPY --from=builder --chown=dify:dify /app/web/.next/static ./targets/next/web/.next/static
COPY --from=builder --chown=dify:dify /app/web/public ./targets/next/web/public
COPY --chown=dify:dify web/docker/entrypoint.sh ./entrypoint.sh
RUN chmod 755 ./entrypoint.sh
USER dify
EXPOSE 3000
ENTRYPOINT ["/bin/sh", "./entrypoint.sh"]
