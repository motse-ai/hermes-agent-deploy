# Linear API 注意事项

## API 基础信息
- Endpoint: `https://api.linear.app/graphql`
- 认证: `Authorization: Bearer $LINEAR_API_KEY`
- 注意: 不要加 "Bearer " 前缀，直接用 `Authorization: $LINEAR_API_KEY`

## 关键发现

### IssueFilter 类型
- 错误: `IssueFilterInput` (Unknown type)
- 正确: `IssueFilter`

### 搜索 Issues
```graphql
query SearchIssues($filter: IssueFilter) {
    issues(first: 5, filter: $filter) {
        nodes {
            id
            identifier
            title
            state { name }
            updatedAt
        }
    }
}
```

变量: `{"filter": {"title": {"contains": "B0GWL9GYHV"}}}`

### 创建 Comment
```graphql
mutation CreateComment($issueId: String!, $body: String!) {
    commentCreate(input: {issueId: $issueId, body: $body}) {
        success
        comment {
            id
            createdAt
        }
    }
}
```

### 父ASIN 到 Linear Issue 的匹配逻辑
- Linear Issue title 包含父ASIN
- 例如: `B0GWL9GYHV` → "星商-科康B0GWL9GYHV, US / VC_WuHan_US" (AMZ-75)
- 一个父ASIN可能匹配多个issue，选择 `updatedAt` 最新那个

### 使用 curl 而非 httpx
在 Python 脚本中使用 `subprocess.run(['curl', ...])` 而非 `httpx.post()`
因为 httpx 的 JSON 序列化可能导致 API 返回 400
