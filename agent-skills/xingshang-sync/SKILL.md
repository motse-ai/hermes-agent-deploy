# xingshang-sync

## 业务背景

**Token Service** 是 **Luckee 2.0** 的后端配置中心，为星商团队的亚马逊广告自动化提供 ASIN 级别的配置管理。

### 核心概念

**Token Service 的作用**：
- 存储每个 ASIN 的广告投放配置（旺通 Profile、领星 ERP 凭证、广告参数）
- Luckee 2.0 读取这些配置，自动执行亚马逊广告操作
- 每个配置项以 **父 ASIN** 为唯一标识（如 `B0F389DLFG`）

**配置项结构**（每个父 ASIN 的配置长这样）：
```json
{
  "id": "B0F389DLFG",
  "title": "奶泡棒MF03 - 美国",
  "config": {
    "PROFILE_ID": "3404420091097881",
    "LINGXING_AUTH_TOKEN": "da97Rv...",
    "LINGXING_COOKIES": { "...": "..." },
    "SKU_LIST": ["MF03-S108040001-US01"],
    "LINGXING_ACCOUNT": "Xianfa",
    "AD_GROUP_ID_FOR_RECOMMENDATION": "333818468726874",
    "COUNTRY": "US",
    "AMAZON_BASE_URL": "amazon.com",
    "target_acos": 0.36,
    "target_daily_sales": 10,
    "daily_budget": 150,
    "EXTRA_REQUIREMENTS": ""
  }
}
```

**关键字段说明**：

| 字段 | 含义 | 示例 |
|------|------|------|
| `id` | 父 ASIN（唯一标识） | `B0F389DLFG` |
| `PROFILE_ID` | 旺通 Profile ID | `3404420091097881` |
| `LINGXING_AUTH_TOKEN` | 领星 ERP 认证 token | `da97Rv...` |
| `LINGXING_COOKIES` | 领星 cookies（含 user_id, company_id 等） | `{ ... }` |
| `SKU_LIST` | SKU 列表 | `["MF03-S108040001-US01"]` |
| `LINGXING_ACCOUNT` | 领星账号名 | `Xianfa` |
| `AD_GROUP_ID_FOR_RECOMMENDATION` | 广告组 ID | `333818468726874` |
| `COUNTRY` | 国家代码 | `US`, `CA`, `UK` |
| `AMAZON_BASE_URL` | Amazon 域名 | `amazon.com` |
| `target_acos` | 目标 ACoS | `0.36` (36%) |
| `target_daily_sales` | 目标日销量 | `10` |
| `daily_budget` | 日预算 | `150` |
| `CONFIG_SOURCE` | 配置来源 | `dingtalk_sync`, `manual` |

### 数据流向

```
钉钉AI表格（星商团队维护）
    ↓ dws aitable record query
Agent 读取
    ↓ 对比 + 构建变更
Token Service MCP
    ↓ create_proposal → approve → execute
Luckee 2.0 自动执行广告操作
```

**钉钉表格字段映射**：

| 字段 ID | 含义 | 对应 Token Service 字段 |
|---------|------|------------------------|
| `7eka1as8zihtzbonwmeka` | 店铺 | 标题中的店铺部分 |
| `l5u9zv2l2yii8rohm53mj` | 父 ASIN | `id` |
| `nu428yf7jdreteb4wa85o` | 子 ASIN 列表 | `SKU_LIST`（需转换） |
| `x6nqwl5skp0smaxa0esw1` | 主推子 ASIN | 需确认用途 |
| `gr613x5xjpt3h8i4elaa6` | 运营人员 | 无直接对应 |
| `7mun3k5ncsj73n837zp4b` | 部门 | 无直接对应 |

### Token Service 现有配置（14个）

当前已配置的 ASIN（供参考）：
- `B0F389DLFG` - 奶泡棒MF03 美国
- `B0F9FS822W` - 奶泡棒MF04 加拿大
- `B0FKBPZB2H` - 拉幕 大衣
- `B01306P1TK` - 拉幕 打底裤
- `B0DTHGSHGB` - 拉幕玩具 复活节
- `B0FKH7R52C` - 星商 COZY地毯
- `B0FHGGQLZN` - 星商 Garvee地毯
- `B091DTM448` - 杨总水杯 CF007 64oz
- `B093KDJXVM` - 杨总水杯 CF007黑色128oz
- `B0CSSR45C6` - 杨总水杯 CF036紫色64oz
- `B0CSSYKXB3` - 杨总水杯 CF037紫色64oz
- `B0DZ26JS8G` - 杨总水杯 CF041紫色32oz
- `B0CZCX5WDC` - 虎一 VC HT04 探针
- `B09JQM7L4T` - 旧配置（仅有 CONFIG_SOURCE）

## 触发条件

- 用户说 "同步星商配置" / "sync xingshang" / "更新星商config"
- 用户问 "Token Service 有哪些 ASIN" / "看看星商配置"
- 用户问 "星商表格和 Token Service 差异" / "对比星商配置"
- 用户 @机器人 提到同步相关关键词

## 工作流程

### Step 1: 读取钉钉 AI 表格

```bash
~/.local/bin/dws aitable record query \
  --base-id nYMoO1rWxaxabEDOCzkx9pRAV47Z3je9 \
  --table-id yiZ7j9V \
  --limit 100
```

**字段解析规则**：
- `7eka1as8zihtzbonwmeka` → 店铺名（如 Garvee_US）
- `l5u9zv2l2yii8rohm53mj` → 父 ASIN（如 B0HGYBQ5KC）
- `nu428yf7jdreteb4wa85o` → 子 ASIN 列表（换行或空格分隔）
- `x6nqwl5skp0smaxa0esw1` → 主推子 ASIN（换行或空格分隔）
- `gr613x5xjpt3h8i4elaa6` → 运营人员
- `7mun3k5ncsj73n837zp4b` → 部门（取 `.name` 字段）

### Step 2: 读取 Token Service 当前配置

使用 `list_configs` MCP 工具获取所有现有配置。

### Step 3: 对比分析

对比逻辑：
1. 以钉钉表格的 **父 ASIN** 为主键
2. 在 Token Service 中查找匹配的 `id`
3. 如果不存在 → 标记为 `create`（新增）
4. 如果存在 → 对比以下字段：
   - 标题（店铺+产品信息）
   - SKU_LIST（子 ASIN 列表）
   - 其他业务字段

**注意**：
- Token Service 的配置可能包含领星凭证等敏感信息，这些字段不在钉钉表格中
- 同步时只更新**业务字段**（标题、SKU 等），不覆盖凭证类字段
- `CONFIG_SOURCE` 字段标记为 `dingtalk_sync` 以区分来源

### Step 4: 创建备份

使用 `create_backup` MCP 工具在修改前创建快照。

### Step 5: 创建提案

使用 `create_proposal` MCP 工具，包含：
- 变更列表（每个 ASIN 的具体变更）
- 变更原因说明
- 等待人工审批

### Step 6: 报告用户

向用户报告：
- 对比结果摘要
- 需要执行的变更数量
- 提案 ID
- 请求审批

### Step 7: 等待审批

**必须等待人工审批**，不能自动执行。用户可以：
- 回复 "批准 {proposal_id}" 或 "approve {proposal_id}"
- 回复 "拒绝 {proposal_id}" 或 "reject {proposal_id}"
- 在 Token Service Web UI 中审批

### Step 8: 执行变更（审批后）

使用 `execute_proposal` MCP 工具执行已批准的提案。

### Step 9: 报告结果

向用户报告执行结果，包括成功/失败的变更。

## 重要规则

1. **必须人工审批** — 所有配置变更都需要人工确认，不可跳过
2. **修改前备份** — 每次修改前创建备份快照
3. **只用 MCP 工具** — 通过 Token Service MCP server 操作，不直接调用 REST API
4. **保护凭证字段** — 不覆盖 LINGXING_AUTH_TOKEN、LINGXING_COOKIES 等敏感字段
5. **标记来源** — 新增配置设置 `CONFIG_SOURCE: dingtalk_sync`
6. **提案 24h 过期** — 未审批的提案自动过期

## 示例对话

**用户**: 同步星商配置
**Bot**: 正在读取钉钉AI表格...
**Bot**: 找到 24 条记录。对比当前 Token Service（14个配置），发现：
  - 钉钉表格有 23 个 ASIN Token Service 中没有
  - Token Service 有 13 个 ASIN 钉钉表格中没有
  - 唯一重叠：B09JQM7L4T（旧配置）
  
  Token Service 的配置包含领星凭证等敏感信息，这些不在钉钉表格中。
  需要确认：是否要将钉钉表格中的 ASIN 新增到 Token Service？
  （需要提供领星凭证等信息才能完整配置）

**用户**: 是的，新增 B0HGYBQ5KC
**Bot**: 好的，请提供以下信息：
  - 旺通 Profile ID
  - 领星账号名
  - SKU 列表
  - 国家
  - 目标 ACoS
  - 日预算
  
  或者，如果只是想在 Token Service 中创建一个占位配置，请回复"先创建空配置"。

**用户**: 先创建空配置
**Bot**: 正在创建备份...
**Bot**: 备份完成 (snapshot: 20260911120000)。已创建提案 (prop_20260911120000_1234)。
  变更内容：
  - 新增 B0HGYBQ5KC（配置来源: dingtalk_sync）
  
  请回复 "批准 prop_20260911120000_1234" 执行变更。

**用户**: 批准 prop_20260911120000_1234
**Bot**: 提案已执行，B0HGYBQ5KC 配置已添加到 Token Service。审计日志已记录。
