# 钉钉表格字段参考

## 表格 baseId
`nYMoO1rWxaxabEDOCzkx9pRAV47Z3je9`

## 表格列表
| 表格ID | 名称 | 记录数 |
|--------|------|--------|
| `ZkXY61H` | 星康&科-旧版本 | - |
| `ibNLijS` | 星商广告投放对齐_康and科_0630更新 | - |
| `vuaLqZ3` | 星商广告投放对齐_康and科_0803更新 (副本) | - |
| `9ewL9q0` | 星商广告投放对齐_康and科_0728更新 (副本) | - |
| `4NyyKJk` | 星商广告投放对齐_康and科_0826更新 | 13条 |
| `yiZ7j9V` | 星商广告投放对齐_康and科_0908 | 9条 |
| `xzgaXpV` | 星商广告投放对齐_康and科_0908 (副本) | - |

## 字段映射 (0826/0908版本通用)

| 字段ID | 字段名 | 类型 | 说明 |
|--------|--------|------|------|
| `7eka1as8zihtzbonwmeka` | 店铺 | text | 如 GarveeT_US, Garvee_US |
| `l5u9zv2l2yii8rohm53mj` | 父ASIN | text | B0GK5HZD16 格式 |
| `nu428yf7jdreteb4wa85o` | 子 asin | text | 换行分隔，B0GF26D4P2\nB0GF29V4RQ... |
| `x6nqwl5skp0smaxa0esw1` | 主推子ASIN | text | 换行分隔 |
| `gr613x5xjpt3h8i4elaa6` | 运营人员 | text | 运营人员姓名 |
| `7mun3k5ncsj73n837zp4b` | 部门 | singleSelect | 星科BG/星康BG/星驰BG/星科二部 |
| `7mD9Mpo` | 创建时间 | createdTime | YYYY-MM-DD 格式 |
| `AQZNqhC` | 更新时间 | lastModifiedTime | YYYY-MM-DD 格式 |
| `uzNYWhw` | 变更信息 | text | 需要同步到Linear的变更内容 |

## 变更信息示例
来自 0826 表格 `lGV7GbrJQC` 记录：
```
父ASIN变更为B0HFJM21ND；去掉了B0GZVSG886和B0GF282DRN
```

## dws CLI 命令
```bash
# 查询记录
dws aitable record query --base-id "nYMoO1rWxaxabEDOCzkx9pRAV47Z3je9" --table-id "4NyyKJk" --limit 100

# 查询字段
dws aitable field list --base-id "nYMoO1rWxaxabEDOCzkx9pRAV47Z3je9" --table-id "4NyyKJk"

# 列出表格
dws aitable table list "nYMoO1rWxaxabEDOCzkx9pRAV47Z3je9"

# 认证状态
dws auth status
```
