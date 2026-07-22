#!/usr/bin/env node
'use strict';

const fs = require('fs');
const path = require('path');
const os = require('os');
const readline = require('readline');
const { spawnSync } = require('child_process');

const { assertConfigured, setupConfig } = require('./lib/config');
const { listVoices, getVoice, addVoice, forgetVoice } = require('./lib/voices');
const { createVoiceClone, synthesizeSpeech, generateScript } = require('./lib/tts');
const { generateVideo } = require('./lib/video');
const { estimateCost, PRICING_UPDATED } = require('./lib/pricing');
const { redact } = require('./lib/security');

const VIDEO_EXTS = ['.mp4', '.mov', '.avi', '.mkv', '.webm'];
const IMAGE_EXTS = ['.jpg', '.jpeg', '.png', '.webp'];

function parseArgs(argv) {
  const args = { _: [] };
  for (let i = 0; i < argv.length; i++) {
    const current = argv[i];
    if (!current.startsWith('--')) { args._.push(current); continue; }
    const key = current.slice(2);
    const next = argv[i + 1];
    if (next === undefined || next.startsWith('--')) args[key] = true;
    else { args[key] = next; i++; }
  }
  return args;
}

function detectModel(inputPath) {
  const ext = path.extname(inputPath).toLowerCase();
  if (VIDEO_EXTS.includes(ext)) return 'videoretalk';
  if (IMAGE_EXTS.includes(ext)) return 'wan2.2-s2v';
  throw new Error(`不支持的输入扩展名 '${ext}'`);
}

function assertInputType(inputPath, model) {
  const ext = path.extname(inputPath).toLowerCase();
  const allowed = model === 'videoretalk' ? VIDEO_EXTS : IMAGE_EXTS;
  if (!allowed.includes(ext)) throw new Error(`${model} 不支持 ${ext || '无扩展名'} 输入`);
}

function getDuration(filePath) {
  const result = spawnSync('ffprobe', ['-v', 'quiet', '-show_entries', 'format=duration', '-of', 'csv=p=0', filePath], { encoding: 'utf8' });
  if (result.status !== 0) return 0;
  return Number.parseFloat(result.stdout.trim()) || 0;
}

function ask(question) {
  const rl = readline.createInterface({ input: process.stdin, output: process.stdout });
  return new Promise(resolve => rl.question(question, answer => { rl.close(); resolve(answer.trim()); }));
}

async function confirmPaidAction(args, summary) {
  console.log(`\n${summary}`);
  console.log('价格仅为估算，更新时间见 pricing.md；最终以阿里云账单为准。');
  if (args['confirm-paid-action'] === true) return true;
  return (await ask('确认执行付费 API 调用? [y/N]: ')).toLowerCase() === 'y';
}

function cmdVoicesList() {
  const voices = listVoices();
  if (!voices.length) return console.log('暂无本地保存的音色。');
  console.log(`本地保存 ${voices.length} 个音色:`);
  for (const v of voices) console.log(`${v.id}\t${v.name}\t${v.aliVoiceId}\t${v.createdAt}`);
}

async function cmdVoicesCreate(args) {
  const cfg = assertConfigured();
  const videoPath = args.from;
  if (!videoPath || !args.name) throw new Error('需要 --from <视频路径> --name <备注名>');
  if (!fs.existsSync(videoPath)) throw new Error(`文件不存在: ${videoPath}`);
  if (!VIDEO_EXTS.includes(path.extname(videoPath).toLowerCase())) throw new Error('声音样本必须是受支持的视频文件');
  const approved = await confirmPaidAction(args, '计划：提取并上传声音样本，创建云端音色。预估费用 ≈ ¥0.01。');
  if (!approved) return console.log('已取消，未调用 API。');
  const { aliVoiceId } = await createVoiceClone({
    apiKey: cfg.apiKey, baseUrl: cfg.baseUrl, enrollmentModel: cfg.voiceEnrollmentModel,
    targetModel: cfg.voiceTargetModel, videoPath, voiceName: args.name
  });
  const record = addVoice({ name: args.name, aliVoiceId, sourceVideo: path.resolve(videoPath) });
  console.log(`音色创建成功: ${record.id} -> ${aliVoiceId}`);
}

function cmdVoicesForget(args) {
  if (!args.id) throw new Error('需要 --id <voice-id>');
  const voice = getVoice(args.id);
  if (!voice) throw new Error(`本地音色记录不存在: ${args.id}`);
  forgetVoice(args.id);
  console.log(`已移除本地记录: ${voice.name} (${args.id})。云端音色未删除。`);
}

async function cmdScriptDraft(args) {
  const cfg = assertConfigured();
  const prompt = args.prompt;
  if (!prompt) throw new Error('需要 --prompt "<主题/需求>"');
  if (!await confirmPaidAction(args, '计划：调用 qwen-plus 生成口播稿，费用按 token 计费。')) return console.log('已取消，未调用 API。');
  const script = await generateScript({ apiKey: cfg.apiKey, baseUrl: cfg.baseUrl, model: cfg.scriptModel, prompt });
  console.log(`--- 文稿 ---\n${script}\n--- 结束 ---\n字数: ${script.length}`);
}

function printEstimate(estimate, model, isNewVoice) {
  console.log(`\n预估费用（价格快照 ${PRICING_UPDATED}）:`);
  if (isNewVoice) console.log(`  声音复刻: ¥${estimate.voice.toFixed(3)}`);
  console.log(`  TTS: ${estimate.chars} 字符 ≈ ¥${estimate.tts.toFixed(4)}`);
  const label = model === 'videoretalk' ? model : `${model} ${estimate.resolution}`;
  console.log(`  ${label}: 按保守时长 ${estimate.seconds.toFixed(1)} 秒 × ¥${estimate.videoRate}/秒 ≈ ¥${estimate.video.toFixed(3)}`);
  console.log(`  合计上限估算: ≈ ¥${estimate.total.toFixed(3)}`);
}

async function cmdGenerate(args) {
  const cfg = assertConfigured();
  const inputPath = args.input;
  const script = args.script;
  if (!inputPath || !script) throw new Error('需要 --input <路径> --script "<文稿>"');
  if (!fs.existsSync(inputPath)) throw new Error(`文件不存在: ${inputPath}`);
  const model = args.model || detectModel(inputPath);
  if (!['videoretalk', 'wan2.2-s2v'].includes(model)) throw new Error(`不支持的模型: ${model}`);
  assertInputType(inputPath, model);
  const resolution = args.resolution || '480P';
  if (!['480P', '720P'].includes(resolution)) throw new Error('分辨率只支持 480P 或 720P');
  if (model === 'videoretalk' && args.resolution) throw new Error('--resolution 仅适用于 wan2.2-s2v');

  let voiceRecord = args.voice ? getVoice(args.voice) : null;
  let aliVoiceId = voiceRecord?.aliVoiceId || null;
  if (args.voice && !voiceRecord) {
    if (!args.voice.startsWith('qwen-tts-')) throw new Error(`音色 ID 不存在: ${args.voice}`);
    aliVoiceId = args.voice;
  }
  const isNewVoice = !aliVoiceId;
  let voiceSourceVideo = args['voice-video'];
  if (isNewVoice) {
    voiceSourceVideo ||= model === 'videoretalk' ? inputPath : null;
    if (!voiceSourceVideo) throw new Error('图片模式新建音色需要 --voice-video <参考视频>');
    if (!fs.existsSync(voiceSourceVideo)) throw new Error(`参考视频不存在: ${voiceSourceVideo}`);
    if (!VIDEO_EXTS.includes(path.extname(voiceSourceVideo).toLowerCase())) throw new Error('声音参考必须是受支持的视频文件');
  }

  const inputDuration = model === 'videoretalk' ? getDuration(inputPath) : 0;
  const speechUpperBound = Math.max(1, script.length / 1.5);
  const estimatedDuration = model === 'videoretalk' ? Math.max(inputDuration, speechUpperBound) : speechUpperBound;
  const estimate = estimateCost({ model, resolution, durationSec: estimatedDuration, scriptChars: script.length, isNewVoice });
  printEstimate(estimate, model, isNewVoice);
  console.log(`计划上传：${path.basename(inputPath)}、TTS 音频${isNewVoice ? `、声音样本 ${path.basename(voiceSourceVideo)}` : ''}`);
  if (!await confirmPaidAction(args, '确认后将依次执行声音复刻（如需）、TTS 和视频生成。')) return console.log('已取消，未上传文件、未调用 API。');

  const tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), 'dh-gen-'));
  try {
    if (isNewVoice) {
      const name = args['voice-name'] || path.basename(voiceSourceVideo, path.extname(voiceSourceVideo));
      const cloned = await createVoiceClone({ apiKey: cfg.apiKey, baseUrl: cfg.baseUrl, enrollmentModel: cfg.voiceEnrollmentModel, targetModel: cfg.voiceTargetModel, videoPath: voiceSourceVideo, voiceName: name });
      aliVoiceId = cloned.aliVoiceId;
      voiceRecord = addVoice({ name, aliVoiceId, sourceVideo: path.resolve(voiceSourceVideo) });
      console.log(`音色已保存: ${voiceRecord.id}`);
    }
    const speech = await synthesizeSpeech({ apiKey: cfg.apiKey, baseUrl: cfg.baseUrl, targetModel: cfg.voiceTargetModel, voiceId: aliVoiceId, text: script, outputDir: tmpDir });
    const timestamp = new Date().toISOString().replace(/[:.]/g, '-').slice(0, 19);
    const outputPath = path.resolve(args.output || `digital-human-${timestamp}.mp4`);
    const result = await generateVideo({
      apiKey: cfg.apiKey, baseUrl: cfg.baseUrl, model, sourcePath: inputPath, audioPath: speech.audioPath,
      outputPath, pollIntervalMs: cfg.pollIntervalMs, maxPollAttempts: cfg.maxPollAttempts,
      extraParams: model === 'videoretalk' ? { video_extension: args.extend !== 'false' } : { resolution }
    });
    console.log(`\n完成: ${outputPath}`);
    console.log(`大小: ${(fs.statSync(outputPath).size / 1024 / 1024).toFixed(1)} MB`);
    console.log(`Task ID: ${result.taskId}`);
  } finally {
    try { fs.rmSync(tmpDir, { recursive: true, force: true }); } catch {}
  }
}

function printHelp() {
  console.log(`数字人视频生成 Skill\n\n用法:\n  node scripts/dh.js config\n  node scripts/dh.js voices list\n  node scripts/dh.js voices create --from <video> --name <名称>\n  node scripts/dh.js voices forget --id <local-id>\n  node scripts/dh.js script-draft --prompt "<主题>"\n  node scripts/dh.js generate --input <视频/图片> --script "<文稿>" [选项]\n\n生成选项:\n  --model videoretalk|wan2.2-s2v\n  --voice <本地ID或阿里音色ID>\n  --voice-video <参考视频>\n  --voice-name <名称>\n  --resolution 480P|720P\n  --extend true|false\n  --output <路径>\n  --confirm-paid-action  已获得用户对本次付费调用的明确批准后使用`);
}

async function main(argv = process.argv.slice(2)) {
  const args = parseArgs(argv);
  try {
    switch (args._[0]) {
      case 'config': return await setupConfig();
      case 'voices':
        if (args._[1] === 'list') return cmdVoicesList();
        if (args._[1] === 'create') return await cmdVoicesCreate(args);
        if (args._[1] === 'forget') return cmdVoicesForget(args);
        throw new Error('用法: voices [list|create|forget]');
      case 'script-draft': return await cmdScriptDraft(args);
      case 'generate': return await cmdGenerate(args);
      case undefined: case 'help': return printHelp();
      default: throw new Error(`未知命令: ${args._[0]}`);
    }
  } catch (err) {
    console.error(`错误: ${redact(err.message)}`);
    if (process.env.DEBUG) console.error(redact(err.stack));
    process.exitCode = 1;
  }
}

if (require.main === module) main();
module.exports = { parseArgs, detectModel, assertInputType, getDuration, confirmPaidAction, cmdGenerate, main };
