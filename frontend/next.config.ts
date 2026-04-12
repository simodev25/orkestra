import type { NextConfig } from "next";

// API_INTERNAL_URL is used server-side (SSR / rewrites running inside Docker).
// NEXT_PUBLIC_API_URL is the browser-facing URL (used by client components).
const apiUrl =
  process.env.API_INTERNAL_URL ||
  process.env.NEXT_PUBLIC_API_URL ||
  "http://localhost:8200";

const nextConfig: NextConfig = {
  async rewrites() {
    return [
      { source: "/api/:path*", destination: `${apiUrl}/api/:path*` },
    ];
  },
  // Increase server-side proxy timeout for long-running LLM calls (test lab)
  serverExternalPackages: [],
  experimental: {
    proxyTimeout: 120_000,
  },
};

export default nextConfig;
