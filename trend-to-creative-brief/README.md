# Trend to Creative Brief

直接检索近期公共 TikTok/Instagram 帖子，按日期、市场、证据强度和品牌适配度筛选趋势，再生成原创广告创意、测试矩阵、风险与过期时间。

## 强依赖：UnifAPI MCP

实时 TikTok/Instagram 研究**强依赖 [UnifAPI MCP](https://unifapi.com/zh/mcp)**。未安装或未完成 OAuth 时，本 Skill 只能处理用户已经提供的证据，不能执行实时社交平台检索。

- MCP Server：`https://mcp.unifapi.com`
- 官方安装与登录：[https://unifapi.com/zh/mcp](https://unifapi.com/zh/mcp)
- 认证：OAuth，只读；不需要向 Skill 粘贴 API Key
- 计费：按返回的公开数据记录计费；执行前以 `get_operation` 返回的 billing 信息和官方价格为准
- 数据边界：只读取公开数据，不发布、不点赞、不登录 TikTok/Instagram 用户账户

本 Skill 不读取、保存或显示 UnifAPI 凭据。实际使用的是当前 Agent 通过 OAuth 连接的 UnifAPI 工作空间；账户与余额归该连接的工作空间所有。

## 启动前检查

实时研究开始前，Agent 必须确认以下 MCP 工具可用：

```text
mcp__unifapi__list_operations
mcp__unifapi__get_operation
mcp__unifapi__call_api
```

然后执行：

1. 用 `list_operations(search="tiktok")` 和 `list_operations(search="instagram")` 读取实时目录。
2. 确认每个请求平台存在公开帖子搜索操作。当前常见路径为：
   - TikTok：`GET /tiktok/search/videos`
   - Instagram：`GET /instagram/search`
3. 用 `get_operation` 检查参数、默认/最大返回量和 billing。
4. 只有上述检查通过后才调用 `call_api`。

检查失败时必须停止实时研究，并说明属于以下哪一种情况：

- UnifAPI MCP 未安装；
- OAuth 未连接或已失效；
- 三个目录工具不完整；
- 实时目录不存在所需平台操作。

不得静默改用浏览器抓取或其他研究 Skill。安装完成后重新运行即可。

## 默认成本控制

- 每个平台先执行一次宽口径查询。
- TikTok 支持 `limit` 时通常从 20 条开始。
- 首次结果为空或明显不相关时，每个平台最多追加一次细化查询。
- 默认不翻页；需要全面研究时由用户明确要求。
- 报告必须记录 query、operation path、request ID、返回数量和 credits charged。

## 使用示例

```text
研究最近 14 天美国 TikTok 和 Instagram 上的夜跑装备趋势，转成广告创意 brief。

查过去 7 天 TikTok 上的 summer running essentials，保留帖子日期、互动量和地域证据。

我已经整理好三个 Reels 链接，不需要实时检索，直接帮我评分并生成测试方案。
```

## 市场与证据规则

- TikTok `region=US` 可作为美国市场证据。
- Instagram 搜索结果常缺少国家字段；即使内容是英文或带 `#usa`，也应标记为 `unverified`。
- 多条内容来自同一卖家，只能证明重复执行，不能证明平台级趋势。
- 播放、点赞和评论是观察值，不是广告效果预测。

## 输出

```text
00_public_social_evidence.json
01_trend_evidence.json
02_trend_scorecard.json
03_creative_brief.md
04_test_matrix.csv
05_risks_and_expiry.md
```

## 本地脚本

公共接口响应可用以下脚本标准化：

```bash
python3 scripts/import_public_social.py \
  --input tiktok-response.json \
  --input instagram-response.json \
  --query "night running gear" \
  --query "night running gear" \
  --from-date 2026-07-01 \
  --to-date 2026-07-14 \
  --market US \
  --output 00_public_social_evidence.json
```

构建广告创意初稿：

```bash
python3 scripts/build_brief.py \
  --brand brand.json \
  --trends trends.json \
  --as-of 2026-07-14 \
  --output-dir outputs/trend-brief
```

脚本仅使用 Python 3.10+ 标准库。

## 验证

```bash
python3 tests/test_smoke.py
```

## License

MIT
