# Isolated, persistent Zoa agent runtime. No secrets are baked into this image.
FROM node:22-alpine
ARG ZOA_STARTER_COMMIT=4016552105862093699c5d20a6aff6255c86fc9c
RUN apk add --no-cache git
WORKDIR /opt/zoa-agent
RUN git init \
 && git remote add origin https://github.com/intuitiontom/zoa-agent-starter.git \
 && git fetch --depth 1 origin "${ZOA_STARTER_COMMIT}" \
 && git checkout --detach FETCH_HEAD
RUN npm ci && npm run typecheck
ENV NODE_ENV=production
CMD ["npm", "start"]
