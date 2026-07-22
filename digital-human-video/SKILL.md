---
name: digital-human-video
description: 使用阿里云百炼将人物视频或照片与口播稿生成数字人口播视频；支持声动人像 videoretalk、万相数字人 wan2.2-s2v、声音复刻、TTS 和口播稿生成。当用户要求制作数字人播报、让照片或视频中的人物说话、复用已授权音色或生成 AI 口播视频时使用。需要 Node.js 18+ 和 ffmpeg，云端调用可能产生费用。
---

# 数字人视频生成

通过 `scripts/dh.js` 调用阿里云百炼。视频输入默认使用 `videoretalk`；图片输入默认使用 `wan2.2-s2v`。

## 安全边界

本 Skill 假设调用者已在流程外取得输入肖像、视频和声音样本的合法使用与克隆授权，不重复进行授权确认。禁止用于欺骗、诈骗、身份验证绕过或未经授权的冒充。建议按发布平台要求标注 AI 生成内容。

所有生成、声音复刻和文稿 API 都可能计费。先向用户展示费用估算、上传文件和调用计划；只有获得本次明确批准后，才可运行交互确认并输入 `y`，或添加 `--confirm-paid-action`。不得自行添加该参数。价格细节按需读取 [references/pricing.md](references/pricing.md)。

## 工作流

1. 运行 `node <skill_dir>/scripts/dh.js voices list` 检查本地音色。
2. 收集输入文件、完整口播稿、模型、音色、分辨率和输出路径。
3. 用户只有主题时，先运行 `script-draft`；展示结果并取得文稿确认。
4. 运行 `generate`，让命令打印保守费用估算和上传计划。
5. 用户明确批准付费调用后再确认执行。等待轮询完成，报告绝对输出路径、文件大小和 Task ID。

## 配置

```bash
node <skill_dir>/scripts/dh.js config
```

配置与音色索引保存在 `~/.config/digital-human-video/`，不会写入 Skill 目录。也可通过环境变量提供 `DASHSCOPE_API_KEY`；官方 Base URL 默认为 `https://dashscope.aliyuncs.com`。工作空间归属由 API Key 决定，不需要 Workspace ID。

自定义 Base URL 会收到 API Key，仅在用户明确确认网关可信时设置 HTTPS 地址和 `DASHSCOPE_ALLOW_CUSTOM_BASE_URL=true`。

## 命令

```bash
# 本地音色索引
node <skill_dir>/scripts/dh.js voices list
node <skill_dir>/scripts/dh.js voices create --from /path/ref.mp4 --name "音色名"
node <skill_dir>/scripts/dh.js voices forget --id <local-id>

# 生成口播稿
node <skill_dir>/scripts/dh.js script-draft --prompt "产品发布口播，轻松自然"

# 视频驱动；不传 voice 时从输入视频创建音色
node <skill_dir>/scripts/dh.js generate \
  --input /path/person.mp4 \
  --script "口播文稿" \
  --output /path/result.mp4

# 图片驱动；新音色需要参考视频
node <skill_dir>/scripts/dh.js generate \
  --input /path/person.jpg \
  --voice-video /path/ref.mp4 \
  --voice-name "音色名" \
  --resolution 480P \
  --script "口播文稿"
```

`voices forget` 只移除本地索引，不删除百炼云端音色。传入已保存的本地 ID 或阿里音色 ID 可复用音色。

## 约束与依赖

- 需要 Node.js 18+、`ffmpeg` 和 `ffprobe`。
- 支持常见 MP4/MOV/MKV/WEBM 视频及 JPG/PNG/WEBP 图片；模型和输入类型必须匹配。
- `wan2.2-s2v` 支持 `480P`（默认）和 `720P`。
- 上传到百炼临时 OSS 的文件按云服务策略保留；不要在日志中输出签名 URL 或凭据。
- 不运行真实 API 作为测试。使用 `npm test` 执行完全离线的安全回归测试。
