const path = require('path');
const { uploadToDashScope } = require('./upload');
const { downloadFile } = require('./download');
const { readJsonResponse, redact } = require('./security');

async function submitTask({ apiKey, baseUrl, model, sourceOssUrl, audioOssUrl, extraParams }) {
  const isVideoRetalk = model === 'videoretalk';
  const payload = isVideoRetalk
    ? {
        model: 'videoretalk',
        input: { video_url: sourceOssUrl, audio_url: audioOssUrl },
        parameters: { video_extension: true, ...(extraParams || {}) }
      }
    : {
        model: 'wan2.2-s2v',
        input: { image_url: sourceOssUrl, audio_url: audioOssUrl },
        parameters: { resolution: '480P', ...(extraParams || {}) }
      };

  const headers = {
    Authorization: `Bearer ${apiKey}`,
    'Content-Type': 'application/json',
    'X-DashScope-Async': 'enable'
  };
  if (sourceOssUrl.startsWith('oss://') || audioOssUrl.startsWith('oss://')) {
    headers['X-DashScope-OssResourceResolve'] = 'enable';
  }

  const resp = await fetch(`${baseUrl}/api/v1/services/aigc/image2video/video-synthesis`, {
    method: 'POST',
    headers,
    body: JSON.stringify(payload)
  });
  const result = await readJsonResponse(resp, 'Video task submit failed');

  const taskId = result.output?.task_id;
  if (!taskId) throw new Error(`No task_id: ${JSON.stringify(redact(result))}`);
  return { taskId, payload };
}

async function pollTask({ apiKey, baseUrl, taskId, intervalMs = 15000, maxAttempts = 80, onProgress }) {
  for (let i = 0; i < maxAttempts; i++) {
    await new Promise(r => setTimeout(r, intervalMs));
    const resp = await fetch(`${baseUrl}/api/v1/tasks/${taskId}`, {
      headers: { Authorization: `Bearer ${apiKey}` }
    });
    const result = await readJsonResponse(resp, 'Poll failed');

    const status = result.output?.task_status;
    if (onProgress) onProgress(i + 1, status, result);
    if (status === 'SUCCEEDED') return result;
    if (['FAILED', 'UNKNOWN', 'CANCELED'].includes(status)) {
      throw new Error(`Task ${status}: ${JSON.stringify(result.output)}`);
    }
  }
  throw new Error(`Polling timed out after ${maxAttempts} attempts`);
}

function downloadResult(url, outputPath) {
  return downloadFile(url, outputPath, { allowedTypes: ['video/', 'application/octet-stream'], maxBytes: 4 * 1024 * 1024 * 1024 });
}

async function generateVideo(opts) {
  const {
    apiKey, baseUrl, model, sourcePath, audioPath,
    outputPath, pollIntervalMs, maxPollAttempts, extraParams
  } = opts;

  // Upload source (video or image) and audio
  const isVideo = model === 'videoretalk';
  console.log(`\n[1/3] 上传${isVideo ? '视频' : '图片'}和音频...`);
  const sourceModel = model;
  const sourceOssUrl = await uploadToDashScope(baseUrl, apiKey, sourcePath, path.basename(sourcePath), sourceModel);
  const audioOssUrl = await uploadToDashScope(baseUrl, apiKey, audioPath, path.basename(audioPath), sourceModel);
  console.log('  源文件与音频已上传到临时 OSS');

  console.log('\n[2/3] 提交视频生成任务...');
  const { taskId } = await submitTask({ apiKey, baseUrl, model, sourceOssUrl, audioOssUrl, extraParams });
  console.log(`  Task ID: ${taskId}`);
  console.log(`  模型: ${model}`);

  console.log('\n[3/3] 等待生成完成...');
  const result = await pollTask({
    apiKey, baseUrl, taskId,
    intervalMs: pollIntervalMs,
    maxAttempts: maxPollAttempts,
    onProgress: (attempt, status) => {
      process.stdout.write(`  [${new Date().toLocaleTimeString()}] 尝试 ${attempt}: ${status}   \r`);
    }
  });

  const videoUrl = result.output?.results?.video_url || result.output?.video_url;
  if (!videoUrl) throw new Error(`No video URL in result: ${JSON.stringify(redact(result))}`);

  console.log(`\n\n下载结果视频...`);
  await downloadResult(videoUrl, outputPath);
  return { outputPath, videoUrl, usage: result.usage, taskId };
}

module.exports = { generateVideo, submitTask, pollTask, downloadResult };
