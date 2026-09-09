# dws 群聊/消息命令速查

## 重要前提

**钉钉没有 MCP 工具** — 所有操作通过 `dws` CLI（终端命令）实现。

## 认证检查

```bash
dws auth status
# 确认 token_valid: true
```

---

## 群消息读取

### 按群名搜索并读取消息

```bash
# 搜索群
dws chat +chat-search --keyword "群名关键词"

# 获取群信息（需要群号/openConversationId）
dws chat +chat-get-by-id --group <群号>

# 读取群消息（分页）
dws chat +chat-messages --group <群号> --limit 50

# 按关键词搜索消息
dws chat +search-msg --keyword "ASIN" --limit 20
```

### 我加入的群列表

```bash
# 列出我加入的所有群
dws chat +my-groups

# 列出所有会话（单聊+群聊）
dws chat +conversation-list --limit 20

# 有未读消息的会话
dws chat +unread-chats
```

---

## 发送消息

```bash
# 发送文本消息到群
dws chat +send-to-group --group <群号> --content "消息内容"

# 机器人发送 Markdown 消息
dws chat +messages-send-by-bot --group <群号> --content "# 标题\n内容"

# 引用回复一条消息
dws chat +messages-reply --message-id <msgId> --content "回复内容"
```

---

## 消息管理

```bash
# 撤回自己发的消息
dws chat +messages-recall --message-id <msgId>

# 机器人撤回群消息
dws chat +messages-batch-recall-by-bot --message-ids <msgId1>,<msgId2>

# 收藏消息
dws chat +flag-create --message-ids <msgId>

# 钉住/取消钉住消息
dws chat +messages-set-pin --message-id <msgId>
```

---

## 常用命令速查

| 操作 | 命令 |
|------|------|
| 搜索群 | `dws chat +chat-search --keyword <关键词>` |
| 读取群消息 | `dws chat +chat-messages --group <群号> --limit 50` |
| 搜索关键词消息 | `dws chat +search-msg --keyword <词> --limit 20` |
| 列出我的群 | `dws chat +my-groups` |
| 发送群消息 | `dws chat +send-to-group --group <群号> --content <内容>` |
| 查询未读 | `dws chat +unread-chats` |
| 读取单聊 | `dws chat +messages-list-direct --open-dingtalk-id <openId> --limit 20` |

---

## 注意事项

- `--format json\|table\|pretty` 可调整输出格式
- `--dry-run` 预览操作不实际执行
- `--yes` 跳过确认提示（AI Agent 模式）
- 消息搜索支持时间范围过滤：`--since`, `--until`
