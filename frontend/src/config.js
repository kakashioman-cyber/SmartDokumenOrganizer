export const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL !== undefined
  ? process.env.NEXT_PUBLIC_API_URL
  : (typeof window !== 'undefined' && window.location.hostname !== 'localhost' ? '' : 'http://localhost:8000');
