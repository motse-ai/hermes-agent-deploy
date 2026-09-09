# linear

Manage Linear project issues, projects, and teams via Linear MCP.

## Trigger

- User mentions Linear, issues, tasks, projects, teams
- "创建issue" / "create issue" / "新建任务"
- "查看进度" / "check progress" / "项目状态"
- "更新issue" / "update issue"

## Available MCP Tools

Use these tools directly — they are provided by Linear MCP:

### Issues
- `list_issues` — Search/filter issues by team, status, assignee
- `get_issue` — Get issue details by ID
- `save_issue` — Create or update an issue

### Projects
- `list_projects` — List all projects
- `get_project` — Get project details

### Teams
- `list_teams` — List all teams
- `get_team` — Get team details

### Other
- `list_issue_statuses` — List workflow statuses
- `list_users` — List team members
- `list_comments` — Get issue comments
- `save_comment` — Add comment to issue

## Team Info

- **Team key**: `LUC` (Luckee2.0)
- Use `team_key: "LUC"` when creating issues

## Workflow

1. User asks about Linear issues/tasks
2. Use `list_issues` with appropriate filters
3. Present results to user
4. If user wants to create/update, use `save_issue`
5. Confirm action to user

## Example

User: 查看LUC团队的进行中任务
Agent: [calls list_issues with team=LUC, status="In Progress"]
Agent: 找到 13 个进行中的任务，以下是前 5 个：
  - T-123: [Issue title] (Assignee: xxx)
  - ...

User: 创建一个新issue
Agent: [calls save_issue with team=LUC, title="...", description="..."]
Agent: 已创建 issue T-456: [title]
