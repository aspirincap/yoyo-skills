const fs = require('fs');
const path = require('path');
const os = require('os');
const { uploadToDashScope } = require('./upload');
const { extractAudioFromVideo, downloadAudio } = require('./audio');
const { readJsonResponse, redact } = require('./security');

async function createVoiceClone({ apiKey, baseUrl, enrollmentModel, targetModel, videoPath, voiceName, note }) {
  // 1. Extract 10-20s audio from video
  const tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), 'dh-voice-'));
  try {
    const audioPath = extractAudioFromVideo(videoPath, tmpDir, 18);
    console.log(`  已提取音频样本: ${(fs.statSync(audioPath).size / 1024).toFixed(0)}KB`);

    // 2. Upload audio
    console.log('  上传音频样本...');
    const audioOssUrl = await uploadToDashScope(baseUrl, apiKey, audioPath, 'voice-sample.wav', enrollmentModel);

    // 3. Enroll voice
    console.log('  调用声音复刻...');
    const sanitized = (voiceName || 'voice').replace(/[^a-zA-Z0-9]/g, '').toLowerCase().slice(0, 8);
    const preferredName = `${sanitized}${Date.now().toString(36).slice(-6)}`;

    const payload = {
      model: enrollmentModel,
      input: {
        action: 'create',
        target_model: targetModel,
        preferred_name: preferredName,
        audio: { data: audioOssUrl }
      }
    };

    const resp = await fetch(`${baseUrl}/api/v1/services/audio/tts/customization`, {
      method: 'POST',
      headers: {
        Authorization: `Bearer ${apiKey}`,
        'Content-Type': 'application/json',
        'X-DashScope-OssResourceResolve': 'enable'
      },
      body: JSON.stringify(payload)
    });
    const result = await readJsonResponse(resp, 'Voice clone failed');

    const aliVoiceId = result.output?.voice || result.output?.voice_id;
    if (!aliVoiceId) throw new Error(`No voice ID returned: ${JSON.stringify(redact(result))}`);
    return { aliVoiceId, audioOssUrl };
  } finally {
    try { fs.rmSync(tmpDir, { recursive: true, force: true }); } catch {}
  }
}

async function synthesizeSpeech({ apiKey, baseUrl, targetModel, voiceId, text, outputDir }) {
  const payload = {
    model: targetModel,
    input: { text, voice: voiceId }
  };

  console.log(`  TTS合成: ${text.length}字符...`);
  const resp = await fetch(`${baseUrl}/api/v1/services/aigc/multimodal-generation/generation`, {
    method: 'POST',
    headers: { Authorization: `Bearer ${apiKey}`, 'Content-Type': 'application/json' },
    body: JSON.stringify(payload)
  });
  const result = await readJsonResponse(resp, 'TTS failed');

  const audioUrl = result.output?.audio?.url || result.output?.audio_url || result.output?.url;
  if (!audioUrl) throw new Error(`No audio URL: ${JSON.stringify(redact(result))}`);

  fs.mkdirSync(outputDir, { recursive: true });
  const audioPath = path.join(outputDir, `tts-${Date.now()}.wav`);
  await downloadAudio(audioUrl, audioPath);
  return { audioPath, audioUrl, characters: result.usage?.characters || text.length };
}

async function generateScript({ apiKey, baseUrl, model, prompt }) {
  const resp = await fetch(`${baseUrl}/compatible-mode/v1/chat/completions`, {
    method: 'POST',
    headers: { Authorization: `Bearer ${apiKey}`, 'Content-Type': 'application/json' },
    body: JSON.stringify({
      model,
      messages: [
        {
          role: 'system',
          content: '你是中文口播稿写作助手。根据用户的主题/需求，写出一段自然、口语化、适合TTS朗读的中文口播稿。只输出文稿正文，不要加任何解释、标题、引号或markdown。控制在20-50秒能读完的长度（大约80-180字）。'
        },
        { role: 'user', content: prompt }
      ],
      temperature: 0.5
    })
  });
  const result = await readJsonResponse(resp, 'Script generation failed');
  return result.choices?.[0]?.message?.content?.trim() || '';
}

module.exports = { createVoiceClone, synthesizeSpeech, generateScript };
