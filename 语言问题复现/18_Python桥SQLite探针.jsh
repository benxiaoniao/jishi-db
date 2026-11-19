# 探针：Python 桥能不能够到真 SQLite（CPython sqlite3 = C 实现的 SQLite）
# 注意：导入 必须写在顶层（函数体里 导入 报 E0201，实测记入语言问题清单）
导入 路径
导入 sqlite3 从 python

打印("sqlite3 类型:", 类型(sqlite3))
打印("connect 类型:", 类型(sqlite3.connect))

令 目 = 路径.临时目录("jsdbpybridge")
令 p = 目 + "/py.db"
令 连 = sqlite3.connect(p)

连.execute("CREATE TABLE t (名 TEXT, 额 REAL)")
连.commit()
连.execute("INSERT INTO t (名, 额) VALUES (?, ?)", ["甲", 1.5])
连.commit()
打印("建表插入: OK")

打印("查询:", 连.execute("SELECT 名, 额 FROM t").fetchall())
打印("参数查询:", 连.execute("SELECT 额 FROM t WHERE 名 = ?", ["甲"]).fetchall())
连.close()
打印("关闭: OK")
