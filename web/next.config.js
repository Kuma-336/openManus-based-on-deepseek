/** @type {import('next').NextConfig} */
const nextConfig = {
  // 将 /api/* 代理到 FastAPI 后端，避免跨域问题
  async rewrites() {
    return [
      {
        source: '/api/:path*',
        destination: 'http://localhost:8000/:path*',
      },
    ]
  },
}

module.exports = nextConfig
