# -*- coding: utf-8 -*-
"""多来源采集入口
用法:
    python run_collect.py                  # 全来源增量
    python run_collect.py --backfill 20000 # 全来源历史回填
    python run_collect.py --only gaoxiaojob --backfill 5000
"""
import argparse
import logging
import os
import sys
import io

import yaml

from collector.fetcher import Fetcher
from collector.store import Store
from collector.scanner import run_scan
from collector.sources import SOURCE_TYPES

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--backfill", type=int, default=0,
                    help="向历史方向回填的 ID 数量")
    ap.add_argument("--only", default=None,
                    help="只运行指定来源（source name）")
    ap.add_argument("--db", default="data/jobs.db")
    ap.add_argument("--config", default="config.yaml")
    ap.add_argument("--log", default=None,
                    help="同时把日志写入该文件（后台回填用）")
    args = ap.parse_args()

    handlers = [logging.StreamHandler()]
    if args.log:
        handlers.append(logging.FileHandler(args.log, encoding="utf-8"))
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(message)s",
                        datefmt="%H:%M:%S", handlers=handlers)

    with open(args.config, encoding="utf-8") as f:
        cfg = yaml.safe_load(f)

    db_dir = os.path.dirname(args.db)
    if db_dir:
        os.makedirs(db_dir, exist_ok=True)
    store = Store(args.db)

    total_found = 0
    for scfg in cfg.get("sources", []):
        if not scfg.get("enabled", True):
            continue
        if args.only and scfg["name"] != args.only:
            continue
        stype = SOURCE_TYPES[scfg["type"]]
        backfill = args.backfill
        if backfill > 0:
            cap = scfg.get("backfill_cap")
            if cap:
                backfill = min(backfill, cap)
            backfill = min(backfill, scfg.get("backfill_max", backfill))
        max_requests = cfg["scan"]["max_requests"]
        if backfill > 0:
            max_requests = max(max_requests, backfill + 100)
        fetcher = Fetcher(base=scfg["base"], timeout=cfg["source_timeout"],
                          min_delay=scfg.get("min_delay", cfg["min_delay"]),
                          max_delay=scfg.get("max_delay", cfg["max_delay"]),
                          max_requests=max_requests)
        source = stype(fetcher, scfg)
        print("== source:", source.name, "backfill:", backfill)
        found, _ = run_scan(fetcher, source, store, cfg, backfill=backfill)
        total_found += found

    print("done: total_found=%d total_jobs=%d"
          % (total_found, len(store.all_jobs())))


if __name__ == "__main__":
    main()
