import type { NextConfig } from "next";

// The browser only ever talks to the Next.js origin; /api/* is proxied to FastAPI.
// This avoids CORS in development and keeps the backend URL out of client bundles.
// Note: rewrites are resolved at build time, so set BACKEND_URL before `next build`.
const backendUrl = process.env.BACKEND_URL ?? "http://127.0.0.1:8000";

const nextConfig: NextConfig = {
  reactStrictMode: true,
  async rewrites() {
    return [{ source: "/api/:path*", destination: `${backendUrl}/api/:path*` }];
  },
};

export default nextConfig;
