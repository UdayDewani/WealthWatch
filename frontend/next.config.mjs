/** @type {import('next').NextConfig} */
const nextConfig = {
  async rewrites() {
    return [
      {
        source: '/api/:path*',
        destination: 'http://localhost:4040/api/:path*',
      },
      {
        source: '/auth',
        destination: 'http://localhost:4040/auth',
      },
      {
        source: '/callback',
        destination: 'http://localhost:4040/callback',
      },
      {
        source: '/ws',
        destination: 'http://localhost:4040/ws',
      },
    ]
  },
  images: {
    unoptimized: true,
  },
  // Give the news pipeline (SearXNG + Firecrawl + LLM) enough time
  experimental: {
    proxyTimeout: 60_000,  // 60 s — news scraping takes ~25-30s
  },
  async headers() {
    return [
      {
        source: '/:path*',
        headers: [
          { key: 'X-Content-Type-Options', value: 'nosniff' },
          { key: 'Referrer-Policy', value: 'strict-origin-when-cross-origin' },
          { key: 'X-Frame-Options', value: 'SAMEORIGIN' },
          {
            key: 'Permissions-Policy',
            value: 'camera=(), microphone=(), geolocation=()',
          },
        ],
      },
    ]
  },
}

export default nextConfig

