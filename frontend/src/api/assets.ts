import type { AssetsData } from '../types/assets';

const BASE = '';

export async function fetchAllAssets(timeoutMs = 30000): Promise<AssetsData> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const res = await fetch(`${BASE}/api/markets/assets`, { signal: controller.signal });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return res.json();
  } finally {
    clearTimeout(timer);
  }
}
