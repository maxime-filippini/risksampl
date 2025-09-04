# Use official Bun image as base
FROM oven/bun:1 AS base

# Set working directory
WORKDIR /app

# Copy package files
COPY package.json bun.lock* ./

# Install dependencies
RUN bun install --frozen-lockfile

# Copy source code
COPY . .

# Build the application
RUN bun run build

# Production stage
FROM oven/bun:1-alpine AS production

WORKDIR /app

# Copy built application from build stage
COPY --from=base /app/build ./build
COPY --from=base /app/package.json ./
COPY --from=base /app/drizzle.config.ts ./
COPY --from=base /app/drizzle ./drizzle
COPY --from=base /app/node_modules ./node_modules

# Expose port 3000
EXPOSE 3000

# Start the application
CMD ["sh", "node build"]