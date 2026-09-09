#!/usr/bin/env python3
"""
钉钉表格变更信息同步到Linear Issue评论

功能：
1. 读取钉钉AI表格中所有记录的变更信息字段
2. 通过父ASIN匹配Linear Issue
3. 将变更信息作为comment同步到对应的Linear Issue

使用方式：
    python sync_change_log_to_linear.py --table-id 4NyyKJk
    python sync_change_log_to_linear.py --table-id yiZ7j9V --dry-run
"""

import json
import argparse
import sys
import os
import subprocess
from datetime import datetime
from typing import Optional

# Linear API配置
LINEAR_API_KEY = os.getenv("LINEAR_API_KEY")
LINEAR_API_URL = "https://api.linear.app/graphql"


def linear_api_query(query: str, variables: dict = None) -> dict:
    """通过curl调用Linear GraphQL API"""
    payload = {"query": query}
    if variables:
        payload["variables"] = variables
    
    cmd = [
        "curl", "-s", "-X", "POST",
        LINEAR_API_URL,
        "-H", f"Authorization: {LINEAR_API_KEY}",
        "-H", "Content-Type: application/json",
        "-d", json.dumps(payload)
    ]
    
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise Exception(f"curl failed: {result.stderr}")
    
    return json.loads(result.stdout)

# 钉钉表格配置
BASE_ID = "nYMoO1rWxaxabEDOCzkx9pRAV47Z3je9"

# 字段映射 (基于4NyyKJk/yiZ7j9V表格)
FIELD_MAPPING = {
    "店铺": "7eka1as8zihtzbonwmeka",
    "父ASIN": "l5u9zv2l2yii8rohm53mj",
    "子ASIN": "nu428yf7jdreteb4wa85o",
    "主推子ASIN": "x6nqwl5skp0smaxa0esw1",
    "运营人员": "gr613x5xjpt3h8i4elaa6",
    "部门": "7mun3k5ncsj73n837zp4b",
    "变更信息": "uzNYWhw",
}


def query_dingtalk_table(table_id: str, limit: int = 100) -> list:
    """通过dws CLI查询钉钉表格"""
    import subprocess
    
    cmd = [
        "dws", "aitable", "record", "query",
        "--base-id", BASE_ID,
        "--table-id", table_id,
        "--limit", str(limit)
    ]
    
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    if result.returncode != 0:
        raise Exception(f"dws command failed: {result.stderr}")
    
    data = json.loads(result.stdout)
    if data.get("status") != "success":
        raise Exception(f"Query failed: {data.get('error', 'Unknown error')}")
    
    return data.get("data", {}).get("records", [])


def search_linear_issue_by_asin(parent_asin: str) -> Optional[dict]:
    """通过父ASIN搜索Linear Issue"""
    query = """
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
    """
    
    # 搜索title中包含该ASIN的issues
    variables = {
        "filter": {
            "title": {"contains": parent_asin}
        }
    }
    
    data = linear_api_query(query, variables)
    issues = data.get("data", {}).get("issues", {}).get("nodes", [])
    
    if not issues:
        # 尝试在description中搜索
        variables = {"filter": {"body": {"contains": parent_asin}}}
        data = linear_api_query(query, variables)
        issues = data.get("data", {}).get("issues", {}).get("nodes", [])
    
    # 返回最新的issue
    if issues:
        return sorted(issues, key=lambda x: x.get("updatedAt", ""), reverse=True)[0]
    return None


def create_linear_comment(issue_id: str, body: str) -> bool:
    """在Linear Issue上创建评论"""
    mutation = """
    mutation CreateComment($issueId: String!, $body: String!) {
        commentCreate(input: {issueId: $issueId, body: $body}) {
            success
            comment {
                id
                createdAt
            }
        }
    }
    """
    
    variables = {"issueId": issue_id, "body": body}
    data = linear_api_query(mutation, variables)
    
    success = data.get("data", {}).get("commentCreate", {}).get("success", False)
    
    if success:
        comment = data.get("data", {}).get("commentCreate", {}).get("comment", {})
        print(f"  [OK] Comment created at {comment.get('createdAt')}")
    
    return success


def format_change_comment(record: dict, table_name: str) -> str:
    """格式化变更信息为Linear comment"""
    cells = record.get("cells", {})
    
    store_name = cells.get(FIELD_MAPPING["店铺"], "")
    parent_asin = cells.get(FIELD_MAPPING["父ASIN"], "")
    sub_asin = cells.get(FIELD_MAPPING["子ASIN"], "")
    main_asin = cells.get(FIELD_MAPPING["主推子ASIN"], "")
    operator = cells.get(FIELD_MAPPING["运营人员"], "")
    department = cells.get(FIELD_MAPPING["部门"], {})
    if isinstance(department, dict):
        department = department.get("name", "")
    change_info = cells.get(FIELD_MAPPING["变更信息"], "")
    record_id = record.get("recordId", "")
    
    # 获取当前时间
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    comment = f"""📋 **钉钉表格变更同步** | {table_name}

⏰ 同步时间：{now}
🔗 来源记录：{record_id}

---

**店铺：** {store_name}
**父ASIN：** `{parent_asin}`
**运营人员：** {operator}
**部门：** {department}

**子ASIN列表：**
{sub_asin}

**主推子ASIN：**
{main_asin}

---

📝 **变更信息：**
{change_info if change_info else '_（无变更）_'}
"""
    return comment


def main():
    parser = argparse.ArgumentParser(description="同步钉钉表格变更信息到Linear Issue")
    parser.add_argument("--table-id", required=True, help="钉钉表格ID")
    parser.add_argument("--dry-run", action="store_true", help="仅显示预览，不实际同步")
    parser.add_argument("--limit", type=int, default=100, help="查询记录数限制")
    args = parser.parse_args()
    
    # 获取表格名称
    table_names = {
        "4NyyKJk": "星商广告投放对齐_康and科_0826更新",
        "yiZ7j9V": "星商广告投放对齐_康and科_0908",
        "ibNLijS": "星商广告投放对齐_康and科_0630更新",
        "ZkXY61H": "星康&科-旧版本",
    }
    table_name = table_names.get(args.table_id, args.table_id)
    
    print(f"\n{'='*60}")
    print(f"📊 钉钉表格变更信息 → Linear Issue Comment 同步")
    print(f"{'='*60}")
    print(f"表格: {table_name} ({args.table_id})")
    print(f"模式: {'🔍 预览 (dry-run)' if args.dry_run else '✅ 实际同步'}")
    print()
    
    # 1. 查询钉钉表格
    print(f"📖 查询钉钉表格...")
    try:
        records = query_dingtalk_table(args.table_id, args.limit)
        print(f"   查到 {len(records)} 条记录")
    except Exception as e:
        print(f"   [ERROR] {e}")
        sys.exit(1)
    
    # 2. 筛选有变更信息的记录
    records_with_changes = []
    for record in records:
        cells = record.get("cells", {})
        change_info = cells.get(FIELD_MAPPING["变更信息"], "")
        if change_info and change_info.strip():
            records_with_changes.append(record)
    
    print(f"   其中 {len(records_with_changes)} 条有变更信息")
    print()
    
    if not records_with_changes:
        print("✅ 没有需要同步的变更信息")
        return
    
    # 3. 处理每条有变更的记录
    print(f"{'='*60}")
    print(f"🔄 开始同步 ({len(records_with_changes)} 条)")
    print(f"{'='*60}")
    
    success_count = 0
    fail_count = 0
    
    for i, record in enumerate(records_with_changes, 1):
        cells = record.get("cells", {})
        parent_asin = cells.get(FIELD_MAPPING["父ASIN"], "")
        store_name = cells.get(FIELD_MAPPING["店铺"], "")
        change_info = cells.get(FIELD_MAPPING["变更信息"], "")
        
        print(f"\n[{i}/{len(records_with_changes)}] {store_name} | {parent_asin}")
        print(f"   变更: {change_info[:80]}{'...' if len(change_info) > 80 else ''}")
        
        # 搜索Linear Issue
        print(f"   🔍 搜索 Linear Issue...")
        issue = search_linear_issue_by_asin(parent_asin)
        
        if not issue:
            print(f"   ⚠️  未找到对应的 Linear Issue")
            fail_count += 1
            continue
        
        print(f"   ✅ 找到: {issue['identifier']} - {issue['title'][:50]}...")
        
        if args.dry_run:
            print(f"   [DRY-RUN] 预览comment内容:")
            comment = format_change_comment(record, table_name)
            print(f"   {'-'*40}")
            for line in comment.split('\n')[:15]:
                print(f"   {line}")
            if len(comment.split('\n')) > 15:
                print(f"   ... (共{len(comment.split(chr(10)))}行)")
            print(f"   {'-'*40}")
            success_count += 1
        else:
            # 创建comment
            comment = format_change_comment(record, table_name)
            print(f"   💬 创建Comment...")
            if create_linear_comment(issue["id"], comment):
                success_count += 1
            else:
                fail_count += 1
    
    # 4. 汇总
    print(f"\n{'='*60}")
    print(f"📊 同步完成")
    print(f"{'='*60}")
    print(f"✅ 成功: {success_count}")
    print(f"❌ 失败: {fail_count}")
    print(f"📝 总计: {len(records_with_changes)}")


if __name__ == "__main__":
    if not LINEAR_API_KEY:
        print("❌ ERROR: LINEAR_API_KEY 环境变量未设置")
        sys.exit(1)
    
    main()