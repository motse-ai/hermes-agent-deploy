# xingshang-sync

## 业务背景

Token Service 是 Luckee 2.0 的后端配置中心，存储星商团队的亚马逊广告 ASIN 配置。

**默认行为**：所有 Token Service 查询默认只返回星商配置（星驰/星商/星乐），无需额外过滤。

## 配置结构

每个配置项以父 ASIN 为唯一标识，包含：
- `XINGSHANG` — 星商标识（name, store_name, campaign_prefix）
- `PARENT_ASIN` — 父 ASIN
- `SPU_ITEM_LIST` — SKU 列表
- `COUNTRY` / `AMAZON_BASE_URL` — 国家和域名
- `target_acos` / `target_daily_sales` / `daily_budget` — 广告参数
- `CAMPAIGN_NAME_PATTERNS` — 广告活动命名规则

## MCP 工具

- `list_configs` — 列出配置（默认 xingshang_only=true）
- `get_config` — 获取单个配置
- `create_proposal` — 创建变更提案（需人工审批）
- `execute_proposal` — 执行已批准的提案

## 工作流程

1. 读取钉钉 AI 表格（星商数据）
2. 调用 `list_configs` 获取当前星商配置
3. 对比差异，构建变更
4. 创建提案，等待人工审批
5. 审批后执行

## 重要规则

1. 所有变更必须人工审批
2. 修改前创建备份
3. 只处理星商配置，不涉及其他团队
