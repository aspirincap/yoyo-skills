'use strict';

const fs = require('fs');
const path = require('path');
const os = require('os');
const readline = require('readline');

const SKILL_ROOT = path.resolve(__dirname, '..', '..');
const CONFIG_DIR = process.env.DIGITAL_HUMAN_CONFIG_DIR || path.join(os.homedir(), '.config', 'digital-human-video');
const ENV_PATH = path.join(CONFIG_DIR, 'config.env');

function parseEnv() {
  const result = {};
  if (!fs.existsSync(ENV_PATH)) return result;
  for (const line of fs.readFileSync(ENV_PATH, 'utf8').split('\n')) {
    const trimmed = line.trim();
    if (!trimmed || trimmed.startsWith('#')) continue;
    const eq = trimmed.indexOf('=');
    if (eq < 0) continue;
    const key = trimmed.slice(0, eq).trim();
    let val = trimmed.slice(eq + 1).trim();
    if ((val.startsWith('"') && val.endsWith('"')) || (val.startsWith("'") && val.endsWith("'"))) val = val.slice(1, -1);
    result[key] = val;
  }
  return result;
}

function validateBaseUrl(rawUrl, allowCustom = false) {
  let parsed;
  try { parsed = new URL(rawUrl); } catch { throw new Error('DASHSCOPE_BASE_URL 必须是有效 URL'); }
  if (parsed.protocol !== 'https:') throw new Error('DASHSCOPE_BASE_URL 必须使用 HTTPS');
  if (parsed.username || parsed.password || parsed.search || parsed.hash) throw new Error('DASHSCOPE_BASE_URL 不能包含凭据、查询参数或片段');
  const official = parsed.hostname === 'dashscope.aliyuncs.com';
  if (!official && !allowCustom) {
    throw new Error('自定义 API 网关可能接收 API Key；确认可信后设置 DASHSCOPE_ALLOW_CUSTOM_BASE_URL=true');
  }
  return parsed.href.replace(/\/$/, '');
}

function getConfig() {
  const saved = parseEnv();
  const value = key => process.env[key] || saved[key];
  const allowCustom = value('DASHSCOPE_ALLOW_CUSTOM_BASE_URL') === 'true';
  return {
    apiKey: value('DASHSCOPE_API_KEY'),
    baseUrl: validateBaseUrl(value('DASHSCOPE_BASE_URL') || 'https://dashscope.aliyuncs.com', allowCustom),
    scriptModel: value('ALI_SCRIPT_MODEL') || 'qwen-plus',
    voiceTargetModel: value('ALI_VOICE_TARGET_MODEL') || 'qwen3-tts-vc-2026-01-22',
    voiceEnrollmentModel: value('ALI_VOICE_ENROLLMENT_MODEL') || 'qwen-voice-enrollment',
    pollIntervalMs: Number(value('ALI_POLL_INTERVAL_MS') || 15000),
    maxPollAttempts: Number(value('ALI_MAX_POLL_ATTEMPTS') || 80)
  };
}

function saveEnv(updates) {
  fs.mkdirSync(CONFIG_DIR, { recursive: true, mode: 0o700 });
  const merged = { ...parseEnv(), ...updates };
  fs.writeFileSync(ENV_PATH, Object.entries(merged).map(([k, v]) => `${k}=${v}`).join('\n') + '\n', { mode: 0o600 });
  fs.chmodSync(ENV_PATH, 0o600);
}

function assertConfigured() {
  const cfg = getConfig();
  if (!cfg.apiKey) throw new Error('DASHSCOPE_API_KEY 未配置。请运行: node scripts/dh.js config');
  return cfg;
}

function ask(question) {
  const rl = readline.createInterface({ input: process.stdin, output: process.stdout });
  return new Promise(resolve => rl.question(question, ans => { rl.close(); resolve(ans.trim()); }));
}

async function setupConfig() {
  const existing = parseEnv();
  console.log('=== 数字人视频生成 Skill 配置 ===\n');
  if (existing.DASHSCOPE_API_KEY) {
    console.log(`当前 API Key: ...${existing.DASHSCOPE_API_KEY.slice(-4)}`);
    if ((await ask('覆盖? [y/N]: ')).toLowerCase() !== 'y') return console.log('保持现有配置。');
  }
  const apiKey = await ask('请输入 DashScope API Key: ');
  if (!apiKey) throw new Error('API Key 不能为空');
  const currentBase = existing.DASHSCOPE_BASE_URL || 'https://dashscope.aliyuncs.com';
  const baseUrl = await ask(`Base URL [${currentBase}]: `);
  const selectedBase = baseUrl || currentBase;
  validateBaseUrl(selectedBase, existing.DASHSCOPE_ALLOW_CUSTOM_BASE_URL === 'true');
  saveEnv({
    DASHSCOPE_API_KEY: apiKey,
    DASHSCOPE_BASE_URL: selectedBase,
    ALI_SCRIPT_MODEL: existing.ALI_SCRIPT_MODEL || 'qwen-plus',
    ALI_VOICE_TARGET_MODEL: existing.ALI_VOICE_TARGET_MODEL || 'qwen3-tts-vc-2026-01-22',
    ALI_VOICE_ENROLLMENT_MODEL: existing.ALI_VOICE_ENROLLMENT_MODEL || 'qwen-voice-enrollment'
  });
  console.log('\n配置已安全保存到', ENV_PATH);
}

module.exports = { getConfig, saveEnv, assertConfigured, setupConfig, validateBaseUrl, SKILL_ROOT, CONFIG_DIR, ENV_PATH };
