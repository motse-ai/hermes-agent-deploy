---
name: xingshang-ad-ops
description: 星商广告运营 - 钉钉表格读取、Linear Issue管理、配置同步
triggers:
  - 星商配置
  - xingshang
  - 钉钉表格同步
  - 变更信息 Linear
---

# 星商广告运营技能 (Xingshang Ad Ops)

## 触发条件
- 用户提到"星商"、"xingshang"配置或广告运营
- 需要同步钉钉表格数据到 Linear
- 需要查询/管理星商店铺、ASIN 配置
- 需要将钉钉表格的变更信息同步到 Linear Issue comment

## 核心能力

### 1. 钉钉 AI 表格读取
读取星商广告投放对齐表格，了解店铺、父ASIN、子ASIN、主推ASIN、变更信息等。

**相关表格 (baseId: `nYMoO1rWxaxabEDOCzkx9pRAV47Z3je9`)：**
| 表格ID | 名称 | 用途 |
|--------|------|------|
| `4NyyKJk` | 星商广告投放对齐_康and科_0826更新 | 0826版本，包含变更信息 |
| `yiZ7j9V` | 星商广告投放对齐_康and科_0908 | 最新版本 |
| `ibNLijS` | 星商广告投放对齐_康and科_0630更新 | 0630版本 |
| `ZkXY61H` | 星康&科-旧版本 | 旧版 |

**字段映射 (0826/0908版本)：**
| 字段ID | 字段名 | 说明 |
|--------|--------|------|
| `7eka1as8zihtzbonwmeka` | 店铺 | store_name |
| `l5u9zv2l2yii8rohm53mj` | 父ASIN | parent_asin |
| `nu428yf7jdreteb4wa85o` | 子ASIN | sub_asin_list |
| `x6nqwl5skp0smaxa0esw1` | 主推子ASIN | main_push_asin_list |
| `gr613x5xjpt3h8i4elaa6` | 运营人员 | operator |
| `7mun3k5ncsj73n837zp4b` | 部门 | department (singleSelect) |
| `uzNYWhw` | 变更信息 | change_info (需要同步到Linear) |

**常用命令：**
```bash
# 查询表格记录
dws aitable record query --base-id "nYMoO1rWxaxabEDOCzkx9pRAV47Z3je9" --table-id "4NyyKJk" --limit 100

# 获取表格字段结构
dws aitable field list --base-id "nYMoO1rWxaxabEDOCzkx9pRAV47Z3je9" --table-id "4NyyKJk"

# 列出所有表格
dws aitable table list "nYMoO1rWxaxabEDOCzkx9pRAV47Z3je9"
```

### 2. Linear Issue 管理
通过 GraphQL API 管理 Linear issues（搜索、创建评论等）。

**关键发现：**
- 父ASIN → Linear Issue title 包含该 ASIN（如 `B0GWL9GYHV` → AMZ-75 "星商-科康B0GWL9GYHV, US"）
- 搜索时用 `IssueFilter` 类型（不是 `IssueFilterInput`）
- Comment 同步格式：变更信息 + 来源记录 + 店铺/ASIN详情

### 3. 变更信息同步到 Linear
将钉钉表格的"变更信息"字段同步到对应 Linear Issue 的 comment。

**执行脚本：**
```bash
# 预览模式（dry-run）
python3 ~/.hermes/skills/amazon-ads/xingshang-ad-ops/scripts/sync_change_log_to_linear.py --table-id 4NyyKJk --dry-run

# 实际同步
python3 ~/.hermes/skills/amazon-ads/xingshang-ad-ops/scripts/sync_change_log_to_linear.py --table-id 4NyyKJk

# 同步最新版本
python3 ~/.hermes/skills/amazon-ads/xingshang-ad-ops/scripts/sync_change_log_to_linear.py --table-id yiZ7j9V
```

**同步逻辑：**
1. 读取钉钉表格，筛选有变更信息（`uzNYWhw` 非空）的记录
2. 通过父ASIN在 Linear issue title 中搜索匹配
3. 格式化变更信息为 comment 内容
4. 在匹配的 Linear Issue 上创建 comment

### 4. 星商配置管理
星商 Token Service 配置（店铺、父ASIN、子ASIN、主推ASIN）。

**配置文件：** `~/hermes-agent/skills/xingshang/xingshang_config.json`

**字段：**
- `store_name`: 店铺名称
- `parent_asin`: 父ASIN
- `sub_asin_list`: 子ASIN列表
- `main_push_asin_list`: 主推子ASIN列表
- `operator`: 运营人员
- `department`: 部门

## 支持文件

- `scripts/sync_change_log_to_linear.py` - 变更信息同步脚本
- `scripts/sync_xingshang_config.py` - 钉钉表格配置同步脚本（较旧）
- `references/xingshang_config.json` - 星商配置本地副本
- `references/dws_chat_commands.md` - dws 群聊/消息命令速查（chat/messages/search）

## 注意事项

- dws CLI 需要已认证：`dws auth status` 确认 `token_valid: true`
- Linear API Key 通过环境变量 `LINEAR_API_KEY` 获取
- 同步前建议先 dry-run 预览
- 一个父ASIN可能匹配多个 Linear Issue，脚本自动选择最新更新的那个
