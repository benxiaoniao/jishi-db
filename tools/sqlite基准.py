# -*- coding: utf-8 -*-
# SQLite 基准（CPython sqlite3 = SQLite C 实现，与 rusqlite 同一引擎内核）
# 用法：python tools/sqlite基准.py
# 输出："名称=值" 行（UTF-8），供 tools/对比基准.jsh 采集。工作负载与 rusqlite 基准一致。
import os
import sqlite3
import sys
import tempfile
import time

sys.stdout.reconfigure(encoding="utf-8")

行数 = 20000
逐行数 = 2000


def 套件(模式):
    d = os.path.join(tempfile.gettempdir(), "jsdb对比基准-sqlite3")
    os.makedirs(d, exist_ok=True)
    p = os.path.join(d, "bench_%s.db" % 模式)
    for 后缀 in ["", "-wal", "-shm"]:
        try:
            os.remove(p + 后缀)
        except OSError:
            pass
    # isolation_level=None = 真 autocommit（每句一提交，与 rusqlite 默认一致）
    连 = sqlite3.connect(p, isolation_level=None)
    if 模式 == "wal":
        连.execute("PRAGMA journal_mode=WAL")
        连.execute("PRAGMA synchronous=NORMAL")
    连.execute("CREATE TABLE 账 (id INTEGER PRIMARY KEY AUTOINCREMENT, 名 TEXT, 额 REAL, 旗 INTEGER)")

    # 1. 批量插入 2 万（一个事务）
    t = time.perf_counter()
    连.execute("BEGIN")
    连.executemany("INSERT INTO 账 (名, 额, 旗) VALUES (?, ?, ?)",
                   [("用户%d" % i, i * 0.5, i % 2) for i in range(行数)])
    连.execute("COMMIT")
    print("批量插入2万=%.6f" % (time.perf_counter() - t))

    # 2. 逐行插入 2 千（autocommit：每行一个隐式事务）
    t = time.perf_counter()
    cur = 连.cursor()
    for i in range(逐行数):
        cur.execute("INSERT INTO 账 (名, 额, 旗) VALUES (?, ?, ?)", ("散客%d" % i, i + 0.25, i % 2))
    print("逐行插入2千=%.6f" % (time.perf_counter() - t))

    # 3. 建索引名
    t = time.perf_counter()
    连.execute("CREATE INDEX idx_名 ON 账(名)")
    print("建索引名=%.6f" % (time.perf_counter() - t))

    # 4. 索引等值 ×500
    t = time.perf_counter()
    命中 = 0
    cur = 连.cursor()
    for k in range(500):
        cur.execute("SELECT id, 名, 额, 旗 FROM 账 WHERE 名 = ?", ("用户%d" % (k % 行数),))
        命中 += len(cur.fetchall())
    print("索引等值x500=%.6f" % (time.perf_counter() - t))
    print("索引等值命中=%d" % 命中)

    # 5. 无索引范围 ×20（额还没索引）
    t = time.perf_counter()
    范命中 = 0
    cur = 连.cursor()
    for k in range(20):
        下 = 9900.0 + k
        cur.execute("SELECT id, 名, 额, 旗 FROM 账 WHERE 额 > ? AND 额 < ?", (下, 下 + 5.0))
        范命中 += len(cur.fetchall())
    print("无索引范围x20=%.6f" % (time.perf_counter() - t))
    print("无索引范围命中=%d" % 范命中)

    # 6. 建索引额
    t = time.perf_counter()
    连.execute("CREATE INDEX idx_额 ON 账(额)")
    print("建索引额=%.6f" % (time.perf_counter() - t))

    # 7. 范围索引 ×200（取行，与引擎同款）
    t = time.perf_counter()
    范索命中 = 0
    cur = 连.cursor()
    for _ in range(200):
        cur.execute("SELECT id, 名, 额, 旗 FROM 账 WHERE 额 > ? AND 额 < ?", (5000.0, 5100.0))
        范索命中 += len(cur.fetchall())
    print("范围索引x200=%.6f" % (time.perf_counter() - t))
    print("范围索引命中=%d" % 范索命中)

    # 8. SQL COUNT WHERE
    t = time.perf_counter()
    数 = 连.execute("SELECT COUNT(*) FROM 账 WHERE 额 > ?", (9000.0,)).fetchone()[0]
    print("SQL_COUNT=%.6f" % (time.perf_counter() - t))
    print("SQL_COUNT命中=%d" % 数)

    # 9. SQL SUM WHERE 旗=1
    t = time.perf_counter()
    总 = 连.execute("SELECT SUM(额) FROM 账 WHERE 旗 = 1", ).fetchone()[0]
    print("SQL_SUM=%.6f" % (time.perf_counter() - t))
    print("SQL_SUM值=%.3f" % 总)

    # 10. 排序取前 5
    t = time.perf_counter()
    行们 = 连.execute("SELECT 名 FROM 账 WHERE id <= ? ORDER BY 额 DESC LIMIT 5", (5000,)).fetchall()
    print("排序2万取前5=%.6f" % (time.perf_counter() - t))
    print("排序命中=%d" % len(行们))

    # 11. 修改（额 > 19000 → 旗 = 1）
    t = time.perf_counter()
    改 = 连.execute("UPDATE 账 SET 旗 = 1 WHERE 额 > ?", (9000.0,)).rowcount
    print("修改2千行=%.6f" % (time.perf_counter() - t))
    print("修改行数=%d" % 改)

    # 12. 事务 500 行提交
    t = time.perf_counter()
    连.execute("BEGIN")
    cur = 连.cursor()
    for i in range(500):
        cur.execute("INSERT INTO 账 (名, 额, 旗) VALUES (?, ?, ?)", ("事务%d" % i, 1.0, 0))
    连.execute("COMMIT")
    print("事务500行提交=%.6f" % (time.perf_counter() - t))

    # 13. 汇总 GROUP BY 旗
    t = time.perf_counter()
    组数 = len(连.execute("SELECT 旗, COUNT(*), SUM(额) FROM 账 GROUP BY 旗").fetchall())
    print("汇总=%.6f" % (time.perf_counter() - t))
    print("汇总组数=%d" % 组数)

    # 14. 关闭 + 重开
    t = time.perf_counter()
    连.close()
    print("关闭=%.6f" % (time.perf_counter() - t))
    t = time.perf_counter()
    连2 = sqlite3.connect(p)
    总条 = 连2.execute("SELECT COUNT(*) FROM 账").fetchone()[0]
    print("重开=%.6f" % (time.perf_counter() - t))
    print("重开条数=%d" % 总条)
    连2.close()
    print("模式=%s" % 模式)


套件("default")
套件("wal")
print("sqlite版本=" + sqlite3.sqlite_version)
