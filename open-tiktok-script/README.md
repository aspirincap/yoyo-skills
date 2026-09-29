# Open TikTok Script

从竞品 TikTok 视频拆解到 Organic、TikTok Shop、Spark Ads、Paid In-Feed 脚本、分镜和 Creator Brief 的完整工作流。

## 灵感来源

本 Skill 的六步工作流、竞品拆解方法和参考库组织，灵感来自花叔（[`alchaincyf`](https://github.com/alchaincyf)）的 [`huashu-douyin-script`](https://github.com/alchaincyf/huashu-skills/tree/master/huashu-douyin-script)。

本次署名核对所依据的固定版本为 [`35e7cf31328f6de07e5d125bfd094791f84b2352`](https://github.com/alchaincyf/huashu-skills/commit/35e7cf31328f6de07e5d125bfd094791f84b2352)（检查日期：2026-07-15）。

`open-tiktok-script` 在此思路上面向海外 TikTok 重新设计，主要新增和改写了：

- TikTok、TikTok Shop、Spark Ads 与 Paid In-Feed 输出类型；
- 英文 creator-native 口语、平台内 CTA 和创作者 Brief；
- 西方语境保护群体、身体焦虑、健康与广告声明安全审校；
- 公共 TikTok 下载、可配置 describe_video 视频分析；
- 原创合成英文示例和待真实数据验证的创意公式库。

完整署名见 [`NOTICE.md`](./NOTICE.md)。

### 授权状态

上游 `alchaincyf/huashu-skills` 在 2026-07-15 检查时没有声明许可证。本项目维护者已于同日确认取得公开发布本改编项目的授权，因此可以发布到 `aspirincap/yoyo-skills`，并继续保留来源署名。该项目级授权不表示上游仓库的其他内容自动获得相同许可证。

## 功能

- 下载并整理最多 5 个公共 TikTok 对标视频；
- 用 describe_video 接口做钩子、分镜、节奏、转化和风险分析；
- 提炼可复用机制，并区分可复制结构与受保护表达；
- 生成 Organic、TikTok Shop、Spark Ads、Paid In-Feed 和 Creator Brief；
- 检查广告声明、版权、文化语境及保护群体风险。

## 依赖

- Python 3.10+
- [`uv`](https://docs.astral.sh/uv/)
- [`yt-dlp`](https://github.com/yt-dlp/yt-dlp)，仅下载公共 TikTok 视频时需要
- 可访问的视频分析服务，默认 `https://agentapi.spotmaxtech.com`
- `ffmpeg` / `ffprobe`，仅本地截取片段时需要

## 配置

复制 `.env.example` 为本 skill 目录的 `.env` 或设置环境变量（环境变量优先）：

- `VIDEO_ANALYSIS_BASE_URL`：服务根地址，默认 `https://agentapi.spotmaxtech.com`。线上部署时配置实际内网地址（HTTP/HTTPS），不猜测或硬编码内部主机名。
- `VIDEO_ANALYSIS_ENV`：默认 `production`，不发送 `X-API-Key`；本地测试显式改为 `local`。
- `VIDEO_ANALYSIS_API_KEY`：仅本地测试使用，不写入仓库或命令示例。线上即使残留该变量也不会发送。

不再读取旧 AI_GATEWAY / GEMINI 配置，也不回退 Google API。运行器使用 Python 标准库，无新增 Python 依赖。

## 数据与隐私边界

- 视频文件或媒体 URL 会发送至配置的分析服务；首次发送前说明目标域名并取得用户授权，当前会话已有授权时不重复询问。
- 不上传含机密、敏感个人信息或未授权人物的视频。
- 默认只下载公开 TikTok 视频。
- 只有用户明确同意时才使用其浏览器 Cookie；不得绕过私密、年龄或地域限制。
- 只分析用户有权访问和使用的内容，遵守 TikTok 条款与当地法律；下载的视频仅用于获准的分析，不随交付物再分发。
- 本地测试使用 HTTPS 和系统证书校验（loopback 测试例外）；线上支持配置内网 HTTP/HTTPS，始终不发送测试 Key。接口重定向被拒绝，测试 Key 不会跟随跳转。
- 代理地址不会写入结果或日志。

## 快速开始

```bash
uv run scripts/download_tiktok.py \
  --urls "https://www.tiktok.com/@creator/video/123" \
  --output-dir _temp/tiktok-downloads

python3 scripts/analyze_video.py \
  --video _temp/tiktok-downloads/tiktok-1-123.mp4 \
  --prompt-file references/video-analysis-prompt.md \
  --profile tiktok \
  --output _temp/tiktok-downloads/analysis-1.md
```

已有媒体直链可改用 `--video-url https://your-media-host.example/video.mp4`（不与 `--video` 同传）。本地测试增加 `--environment local` 并通过环境或 `.env` 配置测试 Key。线上由内网直接访问，不发送该头。外网地址无 Key 返回401是已观察到的访问边界，不代表内网调用也需要 Key；内网连通性需在部署环境验证。

本地截取支持 `--start 2 --end 8`，或 `--start-offset 2s --end-offset 8s`；截取会保留音频，分析时间轴相对片段。旧 `--model`、`--resolution`、`--media-resolution`、`--fps` 和 Gemini 认证/inline 参数均不支持，不会静默忽略。

默认同时保存正文、`<output>.response.json` 和 `<output>.run.json`（请求 ID、用量及完整耗时）。可用 `--response-json` / `--metadata-json` 自定义诊断路径。`--raw-response` 将主输出改为 JSON，仅用于调试；`--dry-run` 不联网。八维缺失、异常长空白或空正文会拒绝作为成功结果；结构通过后仍需核对事实、口播与时间轴。超时不自动重试，已有正文在失败时保留。

如果用户没有竞品视频，可以跳过下载和视频分析，直接用 `references/proven-formulas.md` 作为首轮创意假设。它不是效果保证，后续应使用真实竞品证据或投放数据验证。

## 验证

```bash
python3 tests/test_smoke.py
python3 -m unittest discover -s tests -p test_analyze_video.py -v
```

## 发布前检查

- [x] 已确认取得公开发布本改编项目的授权，并保留来源署名；
- [ ] 未包含 `.env`、Cookie、视频文件、分析产物或缓存；
- [ ] 服务地址及本地/线上认证模式在文档中清晰可配置；
- [ ] 合成脚本示例没有被描述成真实创作者逐字稿；
- [ ] 公式被描述为待验证假设，而非保证效果的“爆款公式”；
- [ ] 离线测试和安全扫描通过。
