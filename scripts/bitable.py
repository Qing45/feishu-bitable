#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
飞书多维表格 CLI —— 读写 Bitable 的最小实现。
凭证走环境变量 FEISHU_APP_ID / FEISHU_APP_SECRET，避免每次传参。

用法:
  python bitable.py info
  python bitable.py tables
  python bitable.py fields   <table_id>
  python bitable.py records  <table_id> [--limit 200]
  python bitable.py create-table <name> --schema schema.json
  python bitable.py add      <table_id> --data records.json [--keys 交易名称,日期]
  python bitable.py delete-table <table_id>
  python bitable.py delete-field <table_id> <field_id>

app_token 由 FEISHU_APP_TOKEN 环境变量或 --app-token 指定。
schema.json   : {"fields":[{...}]}           # 字段顺序即列顺序
records.json  : [{"fields":{...}}, ...] 或 [{"交易名称":...}, ...]
"""
import argparse
import json
import os
import sys
import urllib.error
import urllib.request

API = "https://open.feishu.cn/open-apis"
TOKEN_URL = API + "/auth/v3/tenant_access_token/internal"
BASE = API + "/bitable/v1"


def _http(method, url, token=None, payload=None):
    data = json.dumps(payload, ensure_ascii=False).encode() if payload is not None else None
    headers = {"Content-Type": "application/json; charset=utf-8"}
    if token:
        headers["Authorization"] = "Bearer " + token
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            b = r.read().decode()
            return json.loads(b) if b else {"code": 0}
    except urllib.error.HTTPError as e:
        try:
            return json.loads(e.read().decode())
        except Exception:
            return {"code": e.code, "msg": str(e)}


def token():
    aid = os.environ.get("FEISHU_APP_ID")
    sec = os.environ.get("FEISHU_APP_SECRET")
    if not aid or not sec:
        sys.exit("缺少环境变量 FEISHU_APP_ID / FEISHU_APP_SECRET")
    d = _http("POST", TOKEN_URL, payload={"app_id": aid, "app_secret": sec})
    if d.get("code") != 0:
        sys.exit("取 token 失败: %s %s" % (d.get("code"), d.get("msg")))
    return d["tenant_access_token"]


def app_token(args):
    v = args.app_token or os.environ.get("FEISHU_APP_TOKEN")
    if not v:
        sys.exit("缺少 app_token（--app-token 或 FEISHU_APP_TOKEN）")
    return v


def emit(d, ok_msg="OK"):
    if d.get("code") != 0:
        print("失败 code=%s msg=%s" % (d.get("code"), d.get("msg")))
        sys.exit(1)
    print(ok_msg)


def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def cmd_info(tk, a):
    d = _http("GET", "%s/apps/%s" % (BASE, app_token(a)), tk)
    emit(d)
    print(json.dumps(d.get("data"), ensure_ascii=False, indent=2))


def cmd_tables(tk, a):
    d = _http("GET", "%s/apps/%s/tables?page_size=100" % (BASE, app_token(a)), tk)
    emit(d)
    for t in d.get("data", {}).get("items", []):
        print("%s\t%s" % (t.get("table_id"), t.get("name")))


def cmd_fields(tk, a):
    url = "%s/apps/%s/tables/%s/fields?page_size=100" % (BASE, app_token(a), a.table)
    d = _http("GET", url, tk)
    emit(d)
    for i, f in enumerate(d.get("data", {}).get("items", []), 1):
        print("%2d. %-12s %-14s %s | %s" % (
            i, f.get("field_name"), f.get("ui_type"),
            f.get("field_id"),
            json.dumps(f.get("property"), ensure_ascii=False) if f.get("property") else ""))


def cmd_records(tk, a):
    url = "%s/apps/%s/tables/%s/records?page_size=%d" % (BASE, app_token(a), a.table, a.limit)
    d = _http("GET", url, tk)
    emit(d)
    items = d.get("data", {}).get("items", [])
    print("total=%s shown=%d" % (d.get("data", {}).get("total"), len(items)))
    for it in items:
        print(json.dumps({"record_id": it.get("record_id"), "fields": it.get("fields")},
                         ensure_ascii=False))


def cmd_create_table(tk, a):
    schema = load_json(a.schema)
    fields = schema.get("fields", schema) if isinstance(schema, dict) else schema
    payload = {"table": {"name": a.name, "default_view_name": "表格", "fields": fields}}
    d = _http("POST", "%s/apps/%s/tables" % (BASE, app_token(a)), tk, payload)
    emit(d)
    print("table_id=" + d["data"]["table_id"])


def cmd_add(tk, a):
    raw = load_json(a.data)
    recs = [r if "fields" in r else {"fields": r} for r in raw]
    keys = [k.strip() for k in a.keys.split(",")] if a.keys else []
    if keys:  # 幂等去重
        url = "%s/apps/%s/tables/%s/records?page_size=500" % (BASE, app_token(a), a.table)
        d = _http("GET", url, tk)
        exist = set()
        for it in d.get("data", {}).get("items", []):
            f = it.get("fields", {})
            exist.add(tuple(json.dumps(f.get(k), ensure_ascii=False, sort_keys=True) for k in keys))
        kept = []
        for r in recs:
            f = r["fields"]
            sig = tuple(json.dumps(f.get(k), ensure_ascii=False, sort_keys=True) for k in keys)
            if sig in exist:
                print("跳过已存在: %s" % (sig,))
            else:
                exist.add(sig)
                kept.append(r)
        recs = kept
    if not recs:
        print("无可写入记录（全部已存在）")
        return
    url = "%s/apps/%s/tables/%s/records/batch_create" % (BASE, app_token(a), a.table)
    d = _http("POST", url, tk, {"records": recs})
    emit(d)
    print("写入 %d 条" % len(d["data"].get("records", [])))


def cmd_delete_table(tk, a):
    d = _http("DELETE", "%s/apps/%s/tables/%s" % (BASE, app_token(a), a.table), tk)
    emit(d)


def cmd_delete_field(tk, a):
    url = "%s/apps/%s/tables/%s/fields/%s" % (BASE, app_token(a), a.table, a.field)
    d = _http("DELETE", url, tk)
    emit(d)


def main():
    p = argparse.ArgumentParser(description="飞书多维表格 CLI")
    p.add_argument("--app-token")
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("info")
    sub.add_parser("tables")

    for name in ("fields", "records", "delete-table"):
        s = sub.add_parser(name)
        s.add_argument("table")
        if name == "records":
            s.add_argument("--limit", type=int, default=200)

    s = sub.add_parser("create-table")
    s.add_argument("name")
    s.add_argument("--schema", required=True)

    s = sub.add_parser("add")
    s.add_argument("table")
    s.add_argument("--data", required=True)
    s.add_argument("--keys", help="去重键，逗号分隔，如 交易名称,日期")

    s = sub.add_parser("delete-field")
    s.add_argument("table")
    s.add_argument("field")

    a = p.parse_args()
    tk = token()
    fn = {
        "info": cmd_info, "tables": cmd_tables, "fields": cmd_fields,
        "records": cmd_records, "create-table": cmd_create_table,
        "add": cmd_add, "delete-table": cmd_delete_table, "delete-field": cmd_delete_field,
    }[a.cmd]
    fn(tk, a)


if __name__ == "__main__":
    main()