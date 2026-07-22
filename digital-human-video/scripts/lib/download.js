'use strict';

const fs = require('fs');
const path = require('path');
const { pipeline } = require('stream/promises');

async function downloadFile(url, outputPath, { allowedTypes, maxBytes = 1024 * 1024 * 1024, maxRedirects = 5 } = {}) {
  let current = new URL(url);
  const assertSafeProtocol = target => {
    const localHttp = target.protocol === 'http:' && ['127.0.0.1', '::1', 'localhost'].includes(target.hostname);
    if (target.protocol !== 'https:' && !localHttp) throw new Error('下载 URL 必须使用 HTTPS');
  };
  assertSafeProtocol(current);
  let resp;
  for (let i = 0; i <= maxRedirects; i++) {
    resp = await fetch(current, { redirect: 'manual' });
    if (![301, 302, 303, 307, 308].includes(resp.status)) break;
    if (i === maxRedirects) throw new Error('下载重定向次数过多');
    const location = resp.headers.get('location');
    if (!location) throw new Error('下载重定向缺少 Location');
    current = new URL(location, current);
    assertSafeProtocol(current);
  }
  if (!resp.ok) throw new Error(`下载失败: HTTP ${resp.status}`);
  const type = (resp.headers.get('content-type') || '').split(';')[0].toLowerCase();
  if (allowedTypes?.length && (!type || !allowedTypes.some(prefix => type.startsWith(prefix)))) throw new Error(`下载内容类型不符合预期: ${type || 'missing'}`);
  const declared = Number(resp.headers.get('content-length') || 0);
  if (declared > maxBytes) throw new Error(`下载文件超过大小限制 ${maxBytes} bytes`);
  fs.mkdirSync(path.dirname(path.resolve(outputPath)), { recursive: true });
  const tmp = `${outputPath}.part-${process.pid}-${Date.now()}`;
  let bytes = 0;
  const limiter = new TransformStream({ transform(chunk, controller) {
    bytes += chunk.byteLength;
    if (bytes > maxBytes) throw new Error(`下载文件超过大小限制 ${maxBytes} bytes`);
    controller.enqueue(chunk);
  }});
  try {
    await pipeline(resp.body.pipeThrough(limiter), fs.createWriteStream(tmp, { flags: 'wx' }));
    fs.renameSync(tmp, outputPath);
    return outputPath;
  } catch (err) {
    try { fs.unlinkSync(tmp); } catch {}
    throw err;
  }
}

module.exports = { downloadFile };
