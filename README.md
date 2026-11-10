# feishu-bitable

飞书多维表格（Bitable）读写 Skill，供 AI 助手（DeepSeek Harness 等）完成「凭证 → 建表 → 写数据 → 验证」自动化流程。

## 内容

- `SKILL.md` — 技能说明：前置配置、命令流程、字段格式、排错
- `scripts/bitable.py` — CLI 脚本：取 token、列数据表、查字段、读记录、建表、写入（幂等去重）、删除

## 安装

1. 将本目录整体复制到 AI 助手的技能目录下（DSH Windows 默认为 `<DSH主目录>\.home\skills\feishu-bitable`，路径以本机安装为准）。
2. 本机需有 Python 3（脚本仅用标准库，无第三方依赖）。

## 凭证

通过环境变量注入，**不要提交到任何仓库**：

```
FEISHU_APP_ID=<应用 App ID>
FEISHU_APP_SECRET=<应用 App Secret>
FEISHU_APP_TOKEN=<目标表格链接中的 app_token>
```

首次使用需在飞书开发者后台完成：创建自建应用 → 开通 `bitable:app` 权限 → 发布版本 → 目标表格「添加文档应用」并授予**可编辑**权限。

## 用法示例

```
python scripts/bitable.py tables                                  # 列数据表
python scripts/bitable.py fields <table_id>                       # 查看字段与类型
python scripts/bitable.py records <table_id> --limit 3             # 读取记录
python scripts/bitable.py add <table_id> --data records.json --keys 交易名称,日期   # 幂等写入
```

## 安全

- 凭证只走环境变量或本地私密配置，不入库、不入日志
- 写入一律带 `--keys` 去重，可安全重跑
- `delete-table` / `delete-field` 为破坏性操作，执行前需人工确认
