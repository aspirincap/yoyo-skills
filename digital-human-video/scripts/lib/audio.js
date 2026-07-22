'use strict';

const fs = require('fs');
const path = require('path');
const { spawnSync } = require('child_process');
const { downloadFile } = require('./download');

function ensureFfmpeg() {
  const result = spawnSync('ffmpeg', ['-version'], { stdio: 'ignore' });
  if (result.error?.code === 'ENOENT') throw new Error('ffmpeg not found. Install it first: brew install ffmpeg');
  if (result.status !== 0) throw new Error('ffmpeg 无法运行');
}

function extractAudioFromVideo(videoPath, outputDir, maxSeconds = 20) {
  ensureFfmpeg();
  fs.mkdirSync(outputDir, { recursive: true });
  const outputPath = path.join(outputDir, `voice-${Date.now()}.wav`);
  const result = spawnSync('ffmpeg', [
    '-y', '-i', videoPath, '-t', String(maxSeconds), '-vn',
    '-acodec', 'pcm_s16le', '-ar', '16000', '-ac', '1', outputPath
  ], { stdio: 'pipe', encoding: 'utf8' });
  if (result.status !== 0) throw new Error(`ffmpeg 音频提取失败: ${(result.stderr || '').slice(-500)}`);
  return outputPath;
}

function downloadAudio(url, outputPath) {
  return downloadFile(url, outputPath, { allowedTypes: ['audio/', 'application/octet-stream'], maxBytes: 256 * 1024 * 1024 });
}

module.exports = { extractAudioFromVideo, downloadAudio, ensureFfmpeg };
