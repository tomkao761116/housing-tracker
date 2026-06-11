// API base URL - use env var, or fallback to cloudflared tunnel, or empty for local dev
export const API = process.env.NEXT_PUBLIC_API_URL || 'https://cope-why-peterson-rebound.trycloudflare.com';
