# 24 —— 系统.执行/执行详细 不做标准 argv 引号解析（0.3.5 实测）
# 现象：python -c "import sys; print(sys.argv)" 经 系统.执行详细 跑，python 收到的
# 第一个参数以引号开头（"import… → SyntaxError）；带引号的 exe 路径同样炸
# （tools/对比基准.jsh 起初 rusqlite_bench.exe 路径带引号 → 「不是内部或外部命令」）。
# 结论：引号原样进入参数——带空格/引号的参数都会坏。
# 变通法（本项目已全部落地）：① 参数不带引号（裸路径，路径无空格时可用——对比基准）；
# ② 路径/参数走环境变量（系统.设环境变量 + 子进程 os.environ 读——tools/迁移.jsh）；
# ③ 代码落盘成 .py 再裸调（tests/工具箱_test.jsh 的迁移用例）。
# 单语法点：只测引号传递这一件事。

导入 系统

令 回 = 系统.执行详细(`python -c "import sys; print(sys.argv)"`, 30.0)
打印("A 退出码:", 回["退出码"], "| argv:", 回["输出"], "| err:", 回["错误"])

令 回2 = 系统.执行详细(`python -c "import sys; print(sys.argv)" 甲 "乙 丙"`, 30.0)
打印("B 退出码:", 回2["退出码"], "| argv:", 回2["输出"], "| err:", 回2["错误"])

令 回3 = 系统.执行详细(`cmd /c python -c "import sys; print(sys.argv)"`, 30.0)
打印("C 退出码:", 回3["退出码"], "| argv:", 回3["输出"], "| err:", 回3["错误"])

打印("A 的错误里能看到参数以引号开头（\"import…）即复现成功")
