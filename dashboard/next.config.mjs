/** @type {import('next').NextConfig} */
const nextConfig = {
  output: "standalone",
  async rewrites() {
    // Use internal Docker hostname when available (server-side proxy)
    const apiUrl = process.env.INTERNAL_API_URL || process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
    return [
      {
        source: "/api/v1/local-files/:path*",
        destination: `${apiUrl}/api/v1/local-files/:path*`,
      },
    ];
  },
};

export default nextConfig;
