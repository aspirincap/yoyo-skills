'use strict';

const fs = require('fs');
const path = require('path');
const { CONFIG_DIR } = require('./config');

const VOICES_FILE = path.join(CONFIG_DIR, 'voices.json');

function loadVoices() {
  if (!fs.existsSync(VOICES_FILE)) return [];
  try {
    const parsed = JSON.parse(fs.readFileSync(VOICES_FILE, 'utf8'));
    return Array.isArray(parsed) ? parsed : [];
  } catch { return []; }
}

function saveVoices(voices) {
  fs.mkdirSync(CONFIG_DIR, { recursive: true, mode: 0o700 });
  fs.writeFileSync(VOICES_FILE, JSON.stringify(voices, null, 2) + '\n', { mode: 0o600 });
  fs.chmodSync(VOICES_FILE, 0o600);
}

function listVoices() { return loadVoices().sort((a, b) => b.createdAt.localeCompare(a.createdAt)); }
function getVoice(id) { return loadVoices().find(v => v.id === id); }
function addVoice({ name, aliVoiceId, sourceVideo, note }) {
  const voices = loadVoices();
  const record = {
    id: `v_${Date.now().toString(36)}_${Math.random().toString(36).slice(2, 6)}`,
    name, aliVoiceId, sourceVideo: sourceVideo || '', note: note || '', createdAt: new Date().toISOString()
  };
  voices.push(record);
  saveVoices(voices);
  return record;
}
function forgetVoice(id) { saveVoices(loadVoices().filter(v => v.id !== id)); }

module.exports = { listVoices, getVoice, addVoice, forgetVoice, VOICES_FILE };
