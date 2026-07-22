'use strict';

const PRICING_UPDATED = '2026-07-22';
const RATES = Object.freeze({ voiceClone: 0.01, ttsPer10kChars: 0.8, videoretalkPerSecond: 0.08, wan480PerSecond: 0.5, wan720PerSecond: 0.9 });

function estimateCost({ model, resolution = '480P', durationSec, scriptChars, isNewVoice }) {
  const seconds = Math.max(0, Number(durationSec) || 0);
  const chars = Math.max(0, Number(scriptChars) || 0);
  const voice = isNewVoice ? RATES.voiceClone : 0;
  const tts = chars / 10000 * RATES.ttsPer10kChars;
  const videoRate = model === 'videoretalk'
    ? RATES.videoretalkPerSecond
    : resolution === '720P' ? RATES.wan720PerSecond : RATES.wan480PerSecond;
  const video = seconds * videoRate;
  return { total: voice + tts + video, voice, tts, video, videoRate, seconds, chars, resolution };
}

module.exports = { estimateCost, RATES, PRICING_UPDATED };
