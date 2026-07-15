# Open TikTok Script

从竞品 TikTok 视频拆解到 Organic、TikTok Shop、Spark Ads、Paid In-Feed 脚本、分镜和 Creator Brief 的完整工作流。

## 灵感来源

本 Skill 的六步工作流、竞品拆解方法和参考库组织，灵感来自花叔（[`alchaincyf`](https://github.com/alchaincyf)）的 [`huashu-douyin-script`](https://github.com/alchaincyf/huashu-skills/tree/master/huashu-douyin-script)。

本次署名核对所依据的固定版本为 [`35e7cf31328f6de07e5d125bfd094791f84b2352`](https://github.com/alchaincyf/huashu-skills/commit/35e7cf31328f6de07e5d125bfd094791f84b2352)（检查日期：2026-07-15）。

`open-tiktok-script` 在此思路上面向海外 TikTok 重新设计，主要新增和改写了：

- TikTok、TikTok Shop、Spark Ads 与 Paid In-Feed 输出类型；
- 英文 creator-native 口语、平台内 CTA 和创作者 Brief；
- 西方语境保护群体、身体焦虑、健康与广告声明安全审校；
- 公共 TikTok 下载、可配置 Gemini-compatible 视频分析；
- 原创合成英文示例和待真实数据验证的创意公式库。

完整署名见 [`NOTICE.md`](./NOTICE.md)。

### 授权状态

上游 `alchaincyf/huashu-skills` 在 2026-07-15 检查时没有声明许可证。本项目维护者已于同日确认取得公开发布本改编项目的授权，因此可以发布到 `aspirincap/yoyo-skills`，并继续保留来源署名。该项目级授权不表示上游仓库的其他内容自动获得相同许可证。

## 功能

- 下载并整理最多 5 个公共 TikTok 对标视频；
- 用 Gemini-compatible endpoint 做钩子、分镜、节奏、转化和风险分析；
- 提炼可复用机制，并区分可复制结构与受保护表达；
- 生成 Organic、TikTok Shop、Spark Ads、Paid In-Feed 和 Creator Brief；
- 检查广告声明、版权、文化语境及保护群体风险。

## 依赖

- Python 3.10+
- [`uv`](https://docs.astral.sh/uv/)
- [`yt-dlp`](https://github.com/yt-dlp/yt-dlp)，仅下载公共 TikTok 视频时需要
- 用户配置的 Gemini-compatible 视频分析服务

默认配置使用 Google Gemini API：

```env
GEMINI_VIDEO_API_KEY=replace_with_your_key
GEMINI_VIDEO_BASE_URL=https://generativelanguage.googleapis.com
GEMINI_VIDEO_MODEL=gemini-2.5-flash
GEMINI_VIDEO_AUTH_MODE=x-goog
```

也可以配置兼容网关，并根据网关要求选择 `x-goog`、`bearer` 或 `both`。不要把真实 `.env` 提交到版本库。

## 数据与隐私边界

- 视频分析会把本地视频以 `inlineData` 发送到用户配置的外部 provider；第一次发送前必须说明目标域名并取得用户同意。
- 不上传含机密、敏感个人信息或未授权人物的视频。
- 默认只下载公开 TikTok 视频。
- 只有用户明确同意时才使用其浏览器 Cookie；不得绕过私密、年龄或地域限制。
- 只分析用户有权访问和使用的内容，遵守 TikTok 条款与当地法律；下载的视频仅用于获准的分析，不随交付物再分发。
- 自定义 Gemini-compatible 网关可使用 HTTP 或 HTTPS；使用 HTTPS 时沿用系统默认的证书校验，不内置全局跳过校验参数。
- 代理地址不会写入结果或日志。

## 快速开始

```bash
cp .env.example .env
uv run scripts/download_tiktok.py \
  --urls "https://www.tiktok.com/@creator/video/123" \
  --output-dir _temp/tiktok-downloads

uv run scripts/analyze_video.py \
  --video _temp/tiktok-downloads/tiktok-1-123.mp4 \
  --prompt-file analysis-prompt.md \
  --model flash \
  --resolution medium \
  --output _temp/tiktok-downloads/analysis-1.md
```

如果用户没有竞品视频，可以跳过下载和视频分析，直接用 `references/proven-formulas.md` 作为首轮创意假设。它不是效果保证，后续应使用真实竞品证据或投放数据验证。

## 验证

```bash
python3 tests/test_smoke.py
```

## 发布前检查

- [x] 已确认取得公开发布本改编项目的授权，并保留来源署名；
- [ ] 未包含 `.env`、Cookie、视频文件、分析产物或缓存；
- [ ] 默认 provider、模型和认证方式在文档中清晰可替换；
- [ ] 合成脚本示例没有被描述成真实创作者逐字稿；
- [ ] 公式被描述为待验证假设，而非保证效果的“爆款公式”；
- [ ] 离线测试和安全扫描通过。
