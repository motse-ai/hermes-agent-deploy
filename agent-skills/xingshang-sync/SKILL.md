# xingshang-sync

Sync DingTalk AI Table (星商亚马逊数据表) configs to Token Service with HITL approval.

## Trigger

- User says "同步星商配置" / "sync xingshang" / "更新星商config"
- Bot is @mentioned in group with sync-related keywords
- User asks to check or update xingshang ASIN configs

## Workflow

### Step 1: Read DingTalk AI Table

Use `dws` CLI to query the latest records:

```bash
~/.local/bin/dws aitable record query \
  --base-id nYMoO1rWxaxabEDOCzkx9pRAV47Z3je9 \
  --table-id yiZ7j9V \
  --limit 100
```

Parse records using field ID mapping:
- `7eka1as8zihtzbonwmeka` → store_name (店铺)
- `l5u9zv2l2yii8rohm53mj` → parent_asin (父ASIN)
- `nu428yf7jdreteb4wa85o` → sub_asin_list (子ASIN, comma-separated)
- `x6nqwl5skp0smaxa0esw1` → main_push_asin_list (主推子ASIN, comma-separated)
- `gr613x5xjpt3h8i4elaa6` → operator (运营人员)
- `7mun3k5ncsj73n837zp4b` → department (部门, dict with name field)

### Step 2: Read Current Token Service Configs

Use `list_configs` MCP tool to get all current configs.

### Step 3: Compare and Build Changes

For each DingTalk record:
1. Find matching config by `parent_asin` (config item ID = parent_asin)
2. If not found → action: `create` (will be included in proposal as update)
3. If found → compare fields:
   - `STORE_NAME` vs record's store_name
   - `SUB_ASIN_LIST` vs record's sub_asin_list
   - `MAIN_PUSH_ASIN_LIST` vs record's main_push_asin_list
   - `OPERATOR` vs record's operator
   - `DEPARTMENT` vs record's department
   - `CONFIG_SOURCE` should be `dingtalk_sync`

Build change list:
```python
changes = []
for record in dingtalk_records:
    item_id = record["parent_asin"]
    current = current_configs.get(item_id, {})
    current_cfg = current.get("config", {})
    
    field_map = {
        "STORE_NAME": record["store_name"],
        "SUB_ASIN_LIST": record["sub_asin_list"],
        "MAIN_PUSH_ASIN_LIST": record["main_push_asin_list"],
        "OPERATOR": record["operator"],
        "DEPARTMENT": record["department"],
        "CONFIG_SOURCE": "dingtalk_sync",
    }
    
    for field, new_value in field_map.items():
        old_value = current_cfg.get(field)
        if old_value != new_value:
            changes.append({
                "item_id": item_id,
                "field": field,
                "old_value": old_value,
                "new_value": new_value,
                "action": "update",
            })
```

### Step 4: Create Backup

Use `create_backup` MCP tool before any changes.

### Step 5: Create Proposal

Use `create_proposal` MCP tool with the changes list.

### Step 6: Report to User

Send message to user via DingTalk:
- Number of changes found
- List of affected ASINs
- Proposal ID for tracking
- Ask for approval

### Step 7: Wait for Human Approval

The proposal must be approved by a human before execution. Options:
- User replies "approve {proposal_id}" or "批准 {proposal_id}"
- User replies "reject {proposal_id}" or "拒绝 {proposal_id}"
- User can also approve via Token Service web UI

### Step 8: Execute (if approved)

Use `execute_proposal` MCP tool to apply changes.

### Step 9: Report Result

Send final message with execution results.

## Important Rules

1. **Never skip HITL approval** — all config changes require human approval
2. **Always backup before changes** — create backup before proposal
3. **Use MCP tools only** — never call Token Service REST API directly
4. **Parse DingTalk fields carefully** — department is a dict with `name` key
5. **CONFIG_SOURCE = dingtalk_sync** — mark all synced configs
6. **24h proposal expiration** — unapproved proposals auto-expire

## Example Conversation

User: 同步星商配置
Bot: 正在读取钉钉AI表格...
Bot: 找到 9 条记录。对比当前 Token Service 配置，发现 3 处变更：
  - B09JQM7L4T: SUB_ASIN_LIST 更新
  - B0F389DLFG: 新增配置
  - B0FKBPZB2H: OPERATOR 变更
已创建备份 (snapshot: 20260909123748) 和提案 (prop_20260909123748_8460)。
请回复 "批准 prop_20260909123748_8460" 执行变更，或 "拒绝" 取消。

User: 批准 prop_20260909123748_8460
Bot: 提案已执行，3 处配置已更新。审计日志已记录。
