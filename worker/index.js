const TTL = 60 * 60 * 24 * 90; // 90 days
const CODE_RE = /^[A-Z0-9]{12}$/;
const MAX_IDS = 10000;
const MAX_ID_LEN = 64;

// In-memory rate limit: max 60 writes per IP per minute
const writeCounts = new Map();
function isRateLimited(ip) {
  const now = Date.now();
  const entry = writeCounts.get(ip) || { count: 0, reset: now + 60000 };
  if (now > entry.reset) { entry.count = 0; entry.reset = now + 60000; }
  entry.count++;
  writeCounts.set(ip, entry);
  return entry.count > 60;
}

export default {
  async fetch(request, env) {
    const cors = {
      'Access-Control-Allow-Origin': '*',
      'Access-Control-Allow-Methods': 'GET, PUT, OPTIONS',
      'Access-Control-Allow-Headers': 'Content-Type',
    };

    if (request.method === 'OPTIONS') {
      return new Response(null, { status: 204, headers: cors });
    }

    const parts = new URL(request.url).pathname.split('/').filter(Boolean);
    const code = parts[1];

    if (parts[0] !== 'sync' || !code || !CODE_RE.test(code)) {
      return json({ error: 'not found' }, 404, cors);
    }

    if (request.method === 'GET') {
      const val = await env.SYNC_KV.get(code);
      if (!val) return json({ bookmarks: [], skipped: [], updated_at: null }, 200, cors);
      return new Response(val, { status: 200, headers: { ...cors, 'Content-Type': 'application/json' } });
    }

    if (request.method === 'PUT') {
      const ip = request.headers.get('CF-Connecting-IP') || 'unknown';
      if (isRateLimited(ip)) {
        return json({ error: 'rate limited' }, 429, cors);
      }

      let body;
      try { body = await request.json(); } catch { return json({ error: 'bad json' }, 400, cors); }

      const cleanIds = arr =>
        (Array.isArray(arr) ? arr : [])
          .filter(id => typeof id === 'string' && id.length <= MAX_ID_LEN)
          .slice(0, MAX_IDS);

      const record = JSON.stringify({
        bookmarks: cleanIds(body.bookmarks),
        skipped:   cleanIds(body.skipped),
        updated_at: Date.now(),
      });
      await env.SYNC_KV.put(code, record, { expirationTtl: TTL });
      return new Response(record, { status: 200, headers: { ...cors, 'Content-Type': 'application/json' } });
    }

    return json({ error: 'method not allowed' }, 405, cors);
  },
};

function json(data, status, headers) {
  return new Response(JSON.stringify(data), {
    status,
    headers: { ...headers, 'Content-Type': 'application/json' },
  });
}
