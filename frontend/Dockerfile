FROM node:24-alpine AS build

WORKDIR /web
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
RUN npm run build

FROM nginx:1.29-alpine
ARG NGINX_SITE_CONFIG=nginx.conf
COPY ${NGINX_SITE_CONFIG} /etc/nginx/conf.d/default.conf
COPY cert-reloader.sh /docker-entrypoint.d/40-cert-reloader.sh
COPY --from=build /web/dist /usr/share/nginx/html
RUN chmod 755 /docker-entrypoint.d/40-cert-reloader.sh
EXPOSE 80
