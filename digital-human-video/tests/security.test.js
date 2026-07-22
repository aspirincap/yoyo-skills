'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('fs');
const os = require('os');
const path = require('path');
const http = require('http');
const { spawnSync } = require('child_process');

const ROOT = path.resolve(__dirname, '..');
const CLI = path.join(ROOT, 'scripts', 'dh.js');
const { estimateCost } = require('../scripts/lib/pricing');
const { redact } = require('../scripts/lib/security');
const { validateBaseUrl } = require('../scripts/lib/config');
const { getDuration, detectModel, assertInputType } = require('../scripts/dh');
const { downloadFile } = require('../scripts/lib/download');

test('480P and 720P estimates use the selected resolution', () => {
  const low = estimateCost({ model: 'wan2.2-s2v', resolution: '480P', durationSec: 10, scriptChars: 100, isNewVoice: false });
  const high = estimateCost({ model: 'wan2.2-s2v', resolution: '720P', durationSec: 10, scriptChars: 100, isNewVoice: false });
  assert.equal(low.video, 5);
  assert.equal(high.video, 9);
  assert.equal(low.tts, high.tts);
});

test('Enter alone cancels before any paid API call', () => {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'dh-confirm-'));
  const image = path.join(dir, 'person.jpg');
  fs.writeFileSync(image, 'not-a-real-image');
  const result = spawnSync(process.execPath, [CLI, 'generate', '--input', image, '--script', '测试口播', '--voice', 'qwen-tts-test'], {
    cwd: dir,
    input: '\n',
    encoding: 'utf8',
    timeout: 5000,
    env: { ...process.env, DASHSCOPE_API_KEY: 'offline-test-key', DIGITAL_HUMAN_CONFIG_DIR: path.join(dir, 'config') }
  });
  assert.equal(result.status, 0, result.stderr);
  assert.match(result.stdout, /已取消，未上传文件、未调用 API/);
  assert.doesNotMatch(result.stdout + result.stderr, /fetch failed|ENOTFOUND|HTTP 401/);
  fs.rmSync(dir, { recursive: true, force: true });
});

test('voice creation also confirms before upload or enrollment', () => {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'dh-voice-confirm-'));
  const video = path.join(dir, 'voice.mp4');
  fs.writeFileSync(video, 'not-a-real-video');
  const result = spawnSync(process.execPath, [CLI, 'voices', 'create', '--from', video, '--name', 'test'], {
    cwd: dir,
    input: '\n',
    encoding: 'utf8',
    timeout: 5000,
    env: { ...process.env, DASHSCOPE_API_KEY: 'offline-test-key', DIGITAL_HUMAN_CONFIG_DIR: path.join(dir, 'config') }
  });
  assert.equal(result.status, 0, result.stderr);
  assert.match(result.stdout, /已取消，未调用 API/);
  assert.doesNotMatch(result.stdout + result.stderr, /ffmpeg|fetch failed|ENOTFOUND/);
  fs.rmSync(dir, { recursive: true, force: true });
});

test('hostile filenames are passed as arguments, never through a shell', () => {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'dh-shell-'));
  const marker = path.join(dir, 'owned');
  const hostile = path.join(dir, 'clip";touch owned;#.mp4');
  fs.writeFileSync(hostile, 'x');
  getDuration(hostile);
  assert.equal(fs.existsSync(marker), false);
  fs.rmSync(dir, { recursive: true, force: true });
});

test('model and input validation reject unsupported combinations', () => {
  assert.equal(detectModel('portrait.webp'), 'wan2.2-s2v');
  assert.throws(() => detectModel('portrait.svg'), /不支持/);
  assert.throws(() => assertInputType('portrait.jpg', 'videoretalk'), /不支持/);
});

test('credential-shaped values and signed fields are redacted', () => {
  const value = redact({ apiKey: 'sk-abcdefghijk', nested: { signature: 'secret', message: 'Authorization: Bearer abcdef' } });
  const text = JSON.stringify(value);
  assert.doesNotMatch(text, /abcdefghijk|secret|abcdef/);
  assert.match(text, /REDACTED/);
});

test('custom Base URL requires HTTPS and an explicit trust opt-in', () => {
  assert.equal(validateBaseUrl('https://dashscope.aliyuncs.com/'), 'https://dashscope.aliyuncs.com');
  assert.throws(() => validateBaseUrl('http://dashscope.aliyuncs.com'), /HTTPS/);
  assert.throws(() => validateBaseUrl('https://gateway.example.com'), /自定义 API 网关/);
  assert.equal(validateBaseUrl('https://gateway.example.com/', true), 'https://gateway.example.com');
});

test('404 downloads do not leave output or partial files', async () => {
  const server = http.createServer((_req, res) => { res.writeHead(404, { 'content-type': 'text/html' }); res.end('no'); });
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'dh-download-'));
  const output = path.join(dir, 'result.mp4');
  try {
    await assert.rejects(downloadFile(`http://127.0.0.1:${server.address().port}/missing`, output, { allowedTypes: ['video/'] }), /HTTP 404/);
    assert.equal(fs.existsSync(output), false);
    assert.deepEqual(fs.readdirSync(dir), []);
  } finally {
    server.close();
    fs.rmSync(dir, { recursive: true, force: true });
  }
});

test('successful download is atomic and creates its output directory', async () => {
  const body = Buffer.from('video-bytes');
  const server = http.createServer((_req, res) => { res.writeHead(200, { 'content-type': 'video/mp4', 'content-length': body.length }); res.end(body); });
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'dh-download-ok-'));
  const output = path.join(dir, 'nested', 'result.mp4');
  try {
    await downloadFile(`http://127.0.0.1:${server.address().port}/video`, output, { allowedTypes: ['video/'] });
    assert.deepEqual(fs.readFileSync(output), body);
    assert.deepEqual(fs.readdirSync(path.dirname(output)), ['result.mp4']);
  } finally {
    server.close();
    fs.rmSync(dir, { recursive: true, force: true });
  }
});

test('declared oversized downloads are rejected without a partial file', async () => {
  const server = http.createServer((_req, res) => {
    res.writeHead(200, { 'content-type': 'video/mp4', 'content-length': '999999' });
    res.end('x');
  });
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'dh-download-large-'));
  const output = path.join(dir, 'result.mp4');
  try {
    await assert.rejects(downloadFile(`http://127.0.0.1:${server.address().port}/video`, output, { allowedTypes: ['video/'], maxBytes: 16 }), /超过大小限制/);
    assert.equal(fs.existsSync(output), false);
  } finally {
    server.close();
    fs.rmSync(dir, { recursive: true, force: true });
  }
});
