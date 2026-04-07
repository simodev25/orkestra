import type { NextConfig } from "next";

const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8200";

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
