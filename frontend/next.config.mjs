const embedAllowedOrigins = (
  process.env.NEXT_PUBLIC_TUNEAI_EMBED_ALLOWED_ORIGINS ||
  process.env.TUNEAI_EMBED_ALLOWED_ORIGINS ||
  ""
)
  .split(",")
  .map((origin) => origin.trim().replace(/\/$/, ""))
  .filter(Boolean);

const widgetFrameAncestors = ["'self'", ...embedAllowedOrigins].join(" ");

const nextConfig = {
  output: "standalone",
  async headers() {
    return [
      {
        source: "/widget/:path*",
        headers: [
          {
            key: "Content-Security-Policy",
            value: `frame-ancestors ${widgetFrameAncestors}`
          },
          {
            key: "Permissions-Policy",
            value: "camera=(), geolocation=(), microphone=(self)"
          }
        ]
      }
    ];
  },
  async rewrites() {
    return [
      {
        source: "/api/:path*",
        destination: "http://backend:8000/:path*"
      }
    ];
  }
};

export default nextConfig;
