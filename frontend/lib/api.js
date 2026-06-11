// API base URL - use env var, or fallback to housing-api.cfw.run (cloudflared tunnel), or empty for local dev
export const API = process.env.NEXT_PUBLIC_API_URL || 'https://housing-api.cfw.run';
