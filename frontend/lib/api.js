// API base URL - set via NEXT_PUBLIC_API_URL env var in Cloudflare Pages settings
// Default to backend tunnel for production; local dev overrides via .env.local
export const API = process.env.NEXT_PUBLIC_API_URL || 'https://nights-bali-trademark-explaining.trycloudflare.com';
