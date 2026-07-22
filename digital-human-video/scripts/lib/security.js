'use strict';

const SECRET_KEYS = /api.?key|authorization|signature|policy|access.?key|security.?token|signed.?url/i;

function redact(value) {
  if (typeof value === 'string') {
    return value
      .replace(/Bearer\s+[^\s"']+/gi, 'Bearer [REDACTED]')
      .replace(/sk-[A-Za-z0-9_-]{8,}/g, 'sk-[REDACTED]')
      .replace(/https?:\/\/[^\s"']+[?&](?:Signature|OSSAccessKeyId|SecurityToken)=[^\s"']+/gi, '[REDACTED_SIGNED_URL]');
  }
  if (Array.isArray(value)) return value.map(redact);
  if (value && typeof value === 'object') {
    return Object.fromEntries(Object.entries(value).map(([k, v]) => [k, SECRET_KEYS.test(k) ? '[REDACTED]' : redact(v)]));
  }
  return value;
}

async function readJsonResponse(resp, label) {
  let data;
  try { data = await resp.json(); } catch { throw new Error(`${label}: HTTP ${resp.status}, 返回内容不是 JSON`); }
  if (!resp.ok) throw new Error(`${label}: HTTP ${resp.status} ${JSON.stringify(redact(data))}`);
  return data;
}

module.exports = { redact, readJsonResponse };
