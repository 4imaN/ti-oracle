import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  allowedDevOrigins: ["127.0.0.1"],
  turbopack: {
    root: process.cwd(),
  },
  images: {
    remotePatterns: [
      { protocol: "https", hostname: "cdn.cloudflare.steamstatic.com" },
      { protocol: "https", hostname: "cdn.steamusercontent.com" },
      { protocol: "https", hostname: "avatars.steamstatic.com" },
    ],
  },
};

export default nextConfig;
