# Build stage
FROM node:18-alpine AS build
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm install --legacy-peer-deps
COPY . .
# Default to /api so nginx proxies to the backend on localhost:8000.
ARG VITE_API_URL=/api
ENV VITE_API_URL=$VITE_API_URL
# Leave WS URL empty so useWebSocket.ts derives it from window.location.host at runtime.
ARG VITE_WS_URL=
ENV VITE_WS_URL=$VITE_WS_URL
# Google OAuth client ID — baked into the Vite bundle at build time.
ARG VITE_GOOGLE_CLIENT_ID=
ENV VITE_GOOGLE_CLIENT_ID=$VITE_GOOGLE_CLIENT_ID
RUN npm run build

# Serve stage
FROM nginx:alpine
COPY --from=build /app/dist /usr/share/nginx/html
# NGINX_CONF selects the nginx config:
#   nginx.conf      — local dev (SSL + Docker Compose service-name upstream)
#   nginx.prod.conf — production ECS (HTTP-only + localhost upstream)
ARG NGINX_CONF=nginx.conf
COPY ${NGINX_CONF} /etc/nginx/conf.d/default.conf
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
