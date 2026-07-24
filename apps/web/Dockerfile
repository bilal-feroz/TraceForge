FROM node:22-slim
ENV PNPM_HOME=/pnpm \
    PATH=/pnpm:$PATH \
    NEXT_TELEMETRY_DISABLED=1
RUN corepack enable && corepack prepare pnpm@11.7.0 --activate
ARG NEXT_PUBLIC_TRACEFORGE_API_URL=http://127.0.0.1:8787
ENV NEXT_PUBLIC_TRACEFORGE_API_URL=$NEXT_PUBLIC_TRACEFORGE_API_URL
WORKDIR /workspace
COPY package.json pnpm-workspace.yaml pnpm-lock.yaml ./
COPY apps/web/package.json ./apps/web/package.json
COPY packages/shared-types/package.json ./packages/shared-types/package.json
RUN pnpm install --frozen-lockfile
COPY apps/web ./apps/web
RUN pnpm build
EXPOSE 3000
CMD ["pnpm", "--filter", "@traceforge/web", "start", "--hostname", "0.0.0.0"]
