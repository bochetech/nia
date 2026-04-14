/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  transpilePackages: [],
  async rewrites() {
    return [
      // Proxy API calls to microservices during development
      {
        source: "/api/proxy/tenant-manager/:path*",
        destination: `${process.env.TENANT_MANAGER_URL || "http://localhost:8003"}/api/:path*`,
      },
      {
        source: "/api/proxy/orchestrator/:path*",
        destination: `${process.env.ORCHESTRATOR_URL || "http://localhost:8001"}/v1/:path*`,
      },
      {
        source: "/api/proxy/rag/:path*",
        destination: `${process.env.RAG_URL || "http://localhost:8002"}/v1/rag/:path*`,
      },
      {
        source: "/api/proxy/transcript/:path*",
        destination: `${process.env.TRANSCRIPT_URL || "http://localhost:8008"}/v1/transcripts/:path*`,
      },
    ];
  },
};

module.exports = nextConfig;
