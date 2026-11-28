# -*- coding: utf-8 -*-
# SQLite 源读取腿：由 tools/迁移.jsh 经 系统.执行详细 调起（0.3.5 内置模块不再有 rusqlite）
# 用法：python tools/sqlite迁移.py <SQLite库路径>（argv 1 参；兼容旧环境变量 JSDB_MIGRATE_SRC）
# 输出：一个 JSON 文件路径（UTF-8），内容 {"库": [{"表","字段们","行们","有rowid"}, ...]}
#   行们 = [rowid 或 null, 值…]（rowid 升序）；bytes → {"$字节b64": ...}；NULL → null
import base64
import json
import os
import sqlite3
import sys
import tempfile

sys.stdout.reconfigure(encoding="utf-8")


def 编码值(v):
    if isinstance(v, bytes):
        return {"$字节b64": base64.b64encode(v).decode("ascii")}
    if isinstance(v, float) and (v != v or v == float("inf") or v == float("-inf")):
        return repr(v)  # 非有限小数（极少见）转文本，避免产生非法 JSON
    return v


def 引表(名):
    return '"' + 名.replace('"', '""') + '"'


def 读库(路径):
    连 = sqlite3.connect(路径)
    连.text_factory = str
    try:
        表们 = [r[0] for r in 连.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name")]
        库 = []
        for 名 in 表们:
            字段们 = [r[1] for r in 连.execute("PRAGMA table_info(%s)" % 引表(名))]
            行们 = []
            有rowid = True
            try:
                cur = 连.execute("SELECT rowid, * FROM %s ORDER BY rowid" % 引表(名))
            except sqlite3.OperationalError:
                有rowid = False
            if 有rowid:
                for row in cur:
                    行们.append([row[0]] + [编码值(v) for v in row[1:]])
            else:
                for row in 连.execute("SELECT * FROM %s" % 引表(名)):
                    行们.append([None] + [编码值(v) for v in row])
            库.append({"表": 名, "字段们": 字段们, "行们": 行们, "有rowid": 有rowid})
    finally:
        连.close()
    return {"库": 库}


def 主():
    # 语言 0.3.7 起 jish 侧用 argv 列表形态传路径；环境变量仅作旧版兼容回退
    源 = sys.argv[1] if len(sys.argv) > 1 else os.environ.get("JSDB_MIGRATE_SRC", "")
    if not 源:
        print("缺 SQLite 库路径（argv 1 或环境变量 JSDB_MIGRATE_SRC）", file=sys.stderr)
        return 1
    if not os.path.isfile(源):
        print("SQLite 库不存在: %s" % 源, file=sys.stderr)
        return 1
    数据 = 读库(源)
    出目录 = tempfile.mkdtemp(prefix="jsdb迁移源")
    出 = os.path.join(出目录, "源.json")
    with open(出, "w", encoding="utf-8") as f:
        json.dump(数据, f, ensure_ascii=False)
    print(出)
    return 0


sys.exit(主())
