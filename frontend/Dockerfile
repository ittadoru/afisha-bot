# syntax=docker/dockerfile:1.7
ARG NODE_IMAGE=node:22.22.0-alpine
ARG NGINX_IMAGE=nginx:1.29-alpine

FROM ${NODE_IMAGE} AS build
WORKDIR /app
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --ignore-scripts --no-audit --no-fund
COPY frontend/ ./
ARG VITE_API_BASE_URL=/api
ARG VITE_MAP_STYLE_URL=https://tiles.openfreemap.org/styles/liberty
ENV VITE_API_BASE_URL=${VITE_API_BASE_URL} \
    VITE_MAP_STYLE_URL=${VITE_MAP_STYLE_URL}
RUN npm run api:generate && npm run build

FROM build AS checks
RUN npm test && npm run build-storybook

FROM ${NGINX_IMAGE} AS runtime
COPY frontend/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 8080
