// rusqlite 基准 —— 与 tests/压力_test.jsh / tools/对比基准.jsh 同款工作负载
// 用法：rusqlite_bench.exe <default|wal>
//   default = SQLite 默认配置（delete journal + synchronous FULL）
//   wal     = journal_mode=WAL + synchronous=NORMAL
// 输出：每行 "项目=秒"，供 tools/对比基准.jsh 采集
use rusqlite::{params, Connection};
use std::time::Instant;

fn main() {
    let args: Vec<String> = std::env::args().collect();
    let mode = args.get(1).cloned().unwrap_or_else(|| "default".into());

    let dir = std::env::temp_dir().join("jsdb对比基准-rusqlite");
    std::fs::create_dir_all(&dir).unwrap();
    let path = dir.join(format!("bench_{}.db", mode));
    let _ = std::fs::remove_file(&path);
    let _ = std::fs::remove_file(dir.join(format!("bench_{}.db-wal", mode)));
    let _ = std::fs::remove_file(dir.join(format!("bench_{}.db-shm", mode)));

    let mut conn = Connection::open(&path).unwrap();
    if mode == "wal" {
        conn.pragma_update(None, "journal_mode", "WAL").unwrap();
        conn.pragma_update(None, "synchronous", "NORMAL").unwrap();
    }
    conn.execute_batch("CREATE TABLE 账 (id INTEGER PRIMARY KEY AUTOINCREMENT, 名 TEXT, 额 REAL, 旗 INTEGER)").unwrap();

    // 造数据（不计时）
    let 名们: Vec<String> = (0..20000).map(|i| format!("用户{}", i)).collect();
    let 散客们: Vec<String> = (0..2000).map(|i| format!("散客{}", i)).collect();

    // 1. 批量插入 2 万（一个事务 + 预编译语句）
    let t = Instant::now();
    {
        let tx = conn.transaction().unwrap();
        {
            let mut stmt = tx.prepare("INSERT INTO 账 (名, 额, 旗) VALUES (?1, ?2, ?3)").unwrap();
            for i in 0..20000usize {
                stmt.execute(params![名们[i], i as f64 * 0.5, (i % 2) as i64]).unwrap();
            }
        }
        tx.commit().unwrap();
    }
    println!("批量插入2万={:.6}", t.elapsed().as_secs_f64());

    // 2. 逐行插入 2 千（autocommit：每行一个隐式事务，最贴近逐行落盘语义）
    let t = Instant::now();
    {
        let mut stmt = conn.prepare("INSERT INTO 账 (名, 额, 旗) VALUES (?1, ?2, ?3)").unwrap();
        for i in 0..2000usize {
            stmt.execute(params![散客们[i], i as f64 + 0.25, (i % 2) as i64]).unwrap();
        }
    }
    println!("逐行插入2千={:.6}", t.elapsed().as_secs_f64());

    // 3. 建索引
    let t = Instant::now();
    conn.execute_batch("CREATE INDEX idx_名 ON 账(名)").unwrap();
    println!("建索引名={:.6}", t.elapsed().as_secs_f64());

    // 4. 索引等值 ×500
    let t = Instant::now();
    let mut 命中 = 0usize;
    {
        let mut stmt = conn.prepare("SELECT id, 名, 额, 旗 FROM 账 WHERE 名 = ?1").unwrap();
        for k in 0..500usize {
            let 名 = format!("用户{}", k % 20000);
            let 行们 = stmt.query_map(params![名], |r| r.get::<_, String>(1)).unwrap();
            for _ in 行们 {
                命中 += 1;
            }
        }
    }
    println!("索引等值x500={:.6}", t.elapsed().as_secs_f64());
    println!("索引等值命中={}", 命中);

    // 5. 无索引范围 ×20（额此时还没索引）
    let t = Instant::now();
    let mut 范命中 = 0usize;
    {
        let mut stmt = conn.prepare("SELECT id, 名, 额, 旗 FROM 账 WHERE 额 > ?1 AND 额 < ?2").unwrap();
        for k in 0..20usize {
            let 下 = 9900.0 + k as f64;
            let 行们 = stmt.query_map(params![下, 下 + 5.0], |r| r.get::<_, f64>(2)).unwrap();
            for _ in 行们 {
                范命中 += 1;
            }
        }
    }
    println!("无索引范围x20={:.6}", t.elapsed().as_secs_f64());

    // 6. 范围索引 ×200（含建索引）
    let t = Instant::now();
    conn.execute_batch("CREATE INDEX idx_额 ON 账(额)").unwrap();
    let 建索引额耗时 = t.elapsed().as_secs_f64();
    println!("建索引额={:.6}", 建索引额耗时);
    let t = Instant::now();
    let mut 范索命中 = 0usize;
    {
        let mut stmt = conn.prepare("SELECT id, 名, 额, 旗 FROM 账 WHERE 额 > ?1 AND 额 < ?2").unwrap();
        for _ in 0..200usize {
            let 行们 = stmt.query_map(params![5000.0, 5100.0], |r| r.get::<_, f64>(2)).unwrap();
            for _ in 行们 {
                范索命中 += 1;
            }
        }
    }
    println!("范围索引x200={:.6}", t.elapsed().as_secs_f64());
    println!("范围索引命中={}", 范索命中);

    // 7. SQL COUNT WHERE
    let t = Instant::now();
    let 数: i64 = conn.query_row("SELECT COUNT(*) FROM 账 WHERE 额 > ?1", params![9000.0], |r| r.get(0)).unwrap();
    println!("SQL_COUNT={:.6}", t.elapsed().as_secs_f64());
    println!("SQL_COUNT命中={}", 数);

    // 8. SQL SUM GROUP（旗 分组）
    let t = Instant::now();
    let 总和: f64 = conn.query_row("SELECT SUM(额) FROM 账 WHERE 旗 = 1", params![], |r| r.get(0)).unwrap();
    println!("SQL_SUM_GROUP={:.6}", t.elapsed().as_secs_f64());
    println!("SQL_SUM值={:.3}", 总和);

    // 9. 排序取前 5（ORDER BY 额 DESC）
    let t = Instant::now();
    {
        let mut stmt = conn.prepare("SELECT 名 FROM 账 WHERE id <= ?1 ORDER BY 额 DESC LIMIT 5").unwrap();
        let 行们 = stmt.query_map(params![5000], |r| r.get::<_, String>(0)).unwrap();
        let n = 行们.count();
        println!("排序2万取前5={:.6}", t.elapsed().as_secs_f64());
        println!("排序命中={}", n);
    }

    // 10. 修改 2 千行（额 > 19000 → 1000 行）
    let t = Instant::now();
    let 改 = conn.execute("UPDATE 账 SET 旗 = 1 WHERE 额 > ?1", params![9000.0]).unwrap();
    println!("修改2千行={:.6}", t.elapsed().as_secs_f64());
    println!("修改行数={}", 改);

    // 11. 事务 500 行提交
    let t = Instant::now();
    {
        let tx = conn.transaction().unwrap();
        {
            let mut stmt = tx.prepare("INSERT INTO 账 (名, 额, 旗) VALUES (?1, ?2, ?3)").unwrap();
            for i in 0..500usize {
                stmt.execute(params![format!("事务{}", i), 1.0, 0]).unwrap();
            }
        }
        tx.commit().unwrap();
    }
    println!("事务500行提交={:.6}", t.elapsed().as_secs_f64());

    // 12. 汇总（GROUP BY 旗 全表）
    let t = Instant::now();
    {
        let mut stmt = conn.prepare("SELECT 旗, COUNT(*), SUM(额) FROM 账 GROUP BY 旗").unwrap();
        let 行们 = stmt.query_map(params![], |r| r.get::<_, i64>(0)).unwrap();
        let n = 行们.count();
        println!("汇总={:.6}", t.elapsed().as_secs_f64());
        println!("汇总组数={}", n);
    }

    // 13. 关闭 + 重开
    let t = Instant::now();
    drop(conn);
    println!("关闭={:.6}", t.elapsed().as_secs_f64());
    let t = Instant::now();
    let conn2 = Connection::open(&path).unwrap();
    let 总: i64 = conn2.query_row("SELECT COUNT(*) FROM 账", params![], |r| r.get(0)).unwrap();
    println!("重开={:.6}", t.elapsed().as_secs_f64());
    println!("重开条数={}", 总);
    drop(conn2);
    println!("模式={}", mode);
}
