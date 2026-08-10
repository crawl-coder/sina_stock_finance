#!/usr/bin/python
# -*- coding: UTF-8 -*-
"""
sina_stock_finance 分布式启动脚本
=================================

启动 N 个 Worker 子进程运行 stock_finance 爬虫：
  - 队列: Redis Stream + Consumer Group（settings 已配 CrawloConfig.distributed()）
  - 种子锁: 仅首个 Worker 生成 start_requests，其余跳过
  - 任务分发: 列表页/详情页请求经 Stream 分发给各 Worker
  - 协调退出: 全部空闲后 Leader 广播退出
  - 崩溃回收: 未 ACK 任务由 XCLAIM 自动重投
  - 日志: 各 Worker 使用框架默认文件日志（logs/sina_stock_finance_*.log）

用法：
    python run_distributed.py                # 默认 5 个 Worker
    python run_distributed.py --workers 10   # 指定 Worker 数
    python run_distributed.py --pages 10     # 临时限制爬取页数（冒烟）

前置条件：
    - Redis 运行中（127.0.0.1:6379）
    - 如需 MySQL 入库，确保 MySQL 可用（settings.PIPELINES 已启用 MySQLPipeline）
"""

import argparse
import os
import subprocess
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
RUN_SCRIPT = PROJECT_ROOT / "run.py"
LOG_DIR = PROJECT_ROOT / "logs"


def main():
    parser = argparse.ArgumentParser(description="sina_stock_finance 分布式启动")
    parser.add_argument("--workers", type=int, default=5, help="Worker 数量（默认 5）")
    parser.add_argument("--pages", type=int, default=0,
                        help="临时限制爬取页数（0=使用 spider 默认 MAX_PAGES，冒烟建议 2-5）")
    args = parser.parse_args()

    if args.workers < 1:
        print("❌ Worker 数量必须 >= 1")
        sys.exit(1)

    LOG_DIR.mkdir(parents=True, exist_ok=True)
    python_bin = sys.executable

    print("=" * 72)
    print("  sina_stock_finance 分布式启动")
    print(f"  Python: {python_bin}")
    print(f"  Workers: {args.workers}")
    print(f"  队列: redis_stream（Redis Stream + Consumer Group）")
    if args.pages > 0:
        print(f"  页数限制: {args.pages}（冒烟模式）")
    print(f"  日志目录: {LOG_DIR}（框架默认 logs/sina_stock_finance_*.log）")
    print("=" * 72)

    # 清空上次框架日志，避免汇总读取到旧数据
    for old in LOG_DIR.glob("sina_stock_finance_*.log"):
        old.unlink()

    env = os.environ.copy()
    env["PYTHONPATH"] = str(PROJECT_ROOT)
    if args.pages > 0:
        # 通过 spider 环境变量覆盖 MAX_PAGES（spider 内按需读取）
        env["STOCK_MAX_PAGES"] = str(args.pages)

    processes = []
    worker_logs = {}  # worker_id -> 该 worker 的框架日志文件（启动前后 diff）
    for i in range(1, args.workers + 1):
        # 记录启动前的框架日志集合，用于定位本 worker 的日志文件
        before = set(LOG_DIR.glob("sina_stock_finance_*.log"))
        proc = subprocess.Popen(
            [python_bin, str(RUN_SCRIPT)],
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.STDOUT,
        )
        # 错开启动，等待日志文件出现后再记录归属
        time.sleep(1.5)
        after = set(LOG_DIR.glob("sina_stock_finance_*.log"))
        new_files = sorted(after - before)
        worker_logs[i] = new_files[0] if new_files else None
        processes.append((proc, i))
        log_name = worker_logs[i].name if worker_logs[i] else "(日志未生成)"
        print(f"  Worker {i:02d} started (PID={proc.pid:>6}) -> {log_name}")

    print(f"\n  全部 {len(processes)} 个 Worker 已启动，等待完成…\n")

    results = []
    try:
        for proc, i in processes:
            proc.wait()
            status = "OK" if proc.returncode == 0 else f"FAIL(code={proc.returncode})"
            results.append((i, proc.pid, proc.returncode))
            print(f"  Worker {i:02d} (PID={proc.pid:>6}) {status}")
    except KeyboardInterrupt:
        print("\n  收到中断，终止所有 Worker…")
        for proc, i in processes:
            if proc.poll() is None:
                proc.terminate()
        for proc, i in processes:
            try:
                proc.wait(timeout=8)
            except subprocess.TimeoutExpired:
                proc.kill()
            results.append((i, proc.pid, proc.returncode))

    # 汇总统计
    print("\n" + "=" * 72)
    print("  汇总")
    print("=" * 72)
    success = sum(1 for _, _, rc in results if rc == 0)
    print(f"  Success: {success}   Failed: {len(results) - success}   Total: {len(results)}")

    total_items = 0
    for i, pid, rc in results:
        log_path = worker_logs.get(i)
        if log_path is None or not log_path.exists():
            print(f"\n  [{'OK' if rc == 0 else 'FAIL'}] Worker {i:02d} (PID={pid}): (日志文件缺失)")
            continue
        text = log_path.read_text(encoding="utf-8", errors="ignore")
        # 抓取关键统计
        items = next((line for line in reversed(text.splitlines())
                      if "item_successful_count" in line), "")
        marker = "OK " if rc == 0 else "FAIL"
        print(f"\n  [{marker}] Worker {i:02d} (PID={pid}) {log_path.name}:")
        if items:
            print(f"      {items.strip()}")
            import re
            m = re.search(r"item_successful_count['\"]:\s*(\d+)", items)
            if m:
                total_items += int(m.group(1))
        else:
            print("      (日志未捕获 item 统计)")

    print(f"\n  合计 Item: {total_items}")
    print("=" * 72)


if __name__ == "__main__":
    main()
