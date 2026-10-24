ARG KARA_WEB_PACKAGES_BASE=base
FROM node:24.20.0-alpine AS base
RUN apk add --no-cache tzdata && corepack enable
ENV PNPM_HOME=/pnpm
ENV PATH=/pnpm:$PATH
ENV NEXT_TELEMETRY_DISABLED=1

FROM ${KARA_WEB_PACKAGES_BASE} AS packages
ARG KARA_WEB_OFFLINE=false
WORKDIR /app
COPY package.json pnpm-lock.yaml pnpm-workspace.yaml ./
COPY web/package.json web/package.json
COPY e2e/package.json e2e/package.json
COPY sdks/nodejs-client/package.json sdks/nodejs-client/package.json
COPY cli/package.json cli/package.json
COPY packages packages
RUN if [ "$KARA_WEB_OFFLINE" = "true" ]; then \
      pnpm install --offline --frozen-lockfile --ignore-scripts; \
    else \
      corepack install && pnpm install --frozen-lockfile --ignore-scripts --fetch-timeout=600000 --network-concurrency=8; \
    fi
COPY .company-web/package.json .company-web/package-lock.json .company-web/
RUN if [ "$KARA_WEB_OFFLINE" = "true" ]; then \
      npm ci --offline --prefix .company-web --ignore-scripts --no-audit --no-fund; \
    else \
      npm ci --prefix .company-web --ignore-scripts --no-audit --no-fund; \
    fi

FROM packages AS builder
ARG KARA_WEB_SKIP_CHECKS=false
COPY . .
RUN rm -rf web/.next && if [ "$KARA_WEB_SKIP_CHECKS" != "true" ]; then NODE_OPTIONS=--max-old-space-size=4096 node .company-web/check-projects-types.mjs; fi
RUN node .company-web/localize-literals.mjs web && if [ "$KARA_WEB_SKIP_CHECKS" != "true" ]; then node --test .company-web/rtl.spec.mjs .company-web/members.spec.mjs .company-web/navigation.spec.mjs; fi
WORKDIR /app/web
ENV NODE_OPTIONS=--max-old-space-size=4096
ENV pnpm_config_verify_deps_before_run=false
RUN mkdir -p public/fonts && cp ../.company-web/node_modules/@fontsource-variable/vazirmatn/files/vazirmatn-arabic-wght-normal.woff2 public/fonts/ && cp ../.company-web/node_modules/@fontsource-variable/vazirmatn/LICENSE public/fonts/vazirmatn-license.txt
RUN pnpm exec next build --webpack && rm -rf .next/cache

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
