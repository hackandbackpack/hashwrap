# Multi-stage build for HashWrap React Frontend
FROM node:18-alpine as builder

# Install build dependencies
RUN apk add --no-cache git

# Set working directory
WORKDIR /app

# Copy package files
COPY package*.json ./

# Install dependencies
RUN npm ci --only=production && npm cache clean --force

# Copy source code
COPY . .

# Build the application
RUN npm run build

# Production stage with nginx
FROM nginx:1.25-alpine as production

# Install security updates and cleanup
RUN apk update && apk upgrade && apk add --no-cache tini

# Remove default nginx config
RUN rm /etc/nginx/conf.d/default.conf

# Copy nginx configuration
COPY nginx.conf /etc/nginx/nginx.conf
COPY nginx-site.conf /etc/nginx/conf.d/default.conf

# Copy built application from builder stage
COPY --from=builder /app/dist /usr/share/nginx/html

# Create non-root user for security
RUN addgroup -g 1001 -S hashwrap \
    && adduser -u 1001 -D -S -G hashwrap hashwrap

# Set permissions
RUN chown -R hashwrap:hashwrap /usr/share/nginx/html \
    && chown -R hashwrap:hashwrap /var/cache/nginx \
    && chown -R hashwrap:hashwrap /var/log/nginx \
    && chown -R hashwrap:hashwrap /etc/nginx/conf.d \
    && touch /var/run/nginx.pid \
    && chown -R hashwrap:hashwrap /var/run/nginx.pid

# Create directories for nginx to write to
RUN mkdir -p /var/cache/nginx/client_temp \
    /var/cache/nginx/proxy_temp \
    /var/cache/nginx/fastcgi_temp \
    /var/cache/nginx/uwsgi_temp \
    /var/cache/nginx/scgi_temp \
    && chown -R hashwrap:hashwrap /var/cache/nginx

# Switch to non-root user
USER hashwrap

# Health check
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD wget --no-verbose --tries=1 --spider http://localhost:80/ || exit 1

# Expose port
EXPOSE 80

# Use tini as init system
ENTRYPOINT ["tini", "--"]

# Start nginx
CMD ["nginx", "-g", "daemon off;"]