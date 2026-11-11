import type { NextConfig } from "next";

const API_ORIGIN = process.env.INSIGHTFORGE_API_ORIGIN ?? "http://127.0.0.1:8111";

const nextConfig: NextConfig = {
  cacheComponents: true,
  partialPrefetching: true,
  // The browser talks only to this origin; /api/* is proxied to the FastAPI backend.
  rewrites() {
    return [{ source: "/api/:path*", destination: `${API_ORIGIN}/api/:path*` }];
  },
  turbopack: {
    rules: {
      "*.css": {
        loaders: ["@tailwindcss/turbopack"],
        as: "*.css",
      },
    },
  },
};

export default nextConfig;
