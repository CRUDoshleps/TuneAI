const nextConfig = {
  output: "standalone",
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
