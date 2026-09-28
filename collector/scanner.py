# -*- coding: utf-8 -*-
"""ID 扫描：前沿发现 + 增量/回填（多来源通用，分块并发抓取）"""
import logging

from .parser import match_hits

log = logging.getLogger("collector")

CHUNK = 12


def run_scan(fetcher, source, store, cfg, backfill=0):
    """主流程：ID 扫描型来源走增量/回填；列表型来源走 list_items/fetch_item"""
    if hasattr(source, "list_items"):
        return _run_list_scan(fetcher, source, store)
    return _run_id_scan(fetcher, source, store, cfg, backfill)


def _run_list_scan(fetcher, source, store):
    """列表型来源：列表页 -> 新文章抓详情 -> 全量入库"""
    name = source.name
    items = source.list_items()
    log.info("[%s] list items: %d", name, len(items))
    found = 0
    for aid, title in items:
        if fetcher.dead:
            break
        if store.has_job(aid):
            continue
        job = source.fetch_item(aid)
        if job and store.upsert(job):
            found += 1
            log.info("[%s] hit #%s %s", name, aid, job["title"][:48])
    log.info("[%s] list scan found=%d", name, found)
    return found, len(items)


def _run_id_scan(fetcher, source, store, cfg, backfill=0):
    """ID 扫描型：发现前沿 -> 分块并发扫描未扫过的 ID 段 -> 匹配 -> 存储"""
    name = source.name
    hint = int(store.get_state("frontier_hint:" + name, "0") or 0)
    frontier = source.discover_frontier(hint)
    last = int(store.get_state("scanned_through:" + name, "0") or 0)
    log.info("[%s] frontier=%s scanned_through=%s", name, frontier, last)

    if frontier <= 0:
        log.warning("[%s] frontier discovery failed", name)
        return 0, 0
    store.set_state("frontier_hint:" + name, frontier)

    window = cfg["scan"]["daily_window"]
    scan_start = scan_end = None
    if last == 0:
        size = backfill or window
        scan_start = max(1, frontier - size + 1)
        scan_end = frontier
    elif backfill > 0:
        bf = int(store.get_state("backfilled_through:" + name, "0") or 0)
        scan_end = (bf - 1) if bf else last
        scan_start = max(1, scan_end - backfill + 1)
    else:
        if frontier > last:
            scan_start = last + 1
            scan_end = min(frontier, last + window)

    found = checked = 0
    lowest = None
    if scan_start is not None:
        # 降序分块（从新到旧）；配额中断时指针落在最后已扫 ID，不留空隙
        ids = list(range(scan_end, scan_start - 1, -1))
        for i in range(0, len(ids), CHUNK):
            chunk = ids[i:i + CHUNK]
            results = fetcher.get_many(
                [source.detail_path(a) for a in chunk])
            for aid, r in zip(chunk, results):
                checked += 1
                lowest = aid
                data = source.parse_response(r, aid)
                if data == "invalid":
                    continue
                hits = match_hits(data, cfg)
                if not hits:
                    hits = match_hits(_augmented(source, data), cfg)
                if hits:
                    data["matched_keywords"] = hits
                    if store.upsert(data):
                        found += 1
                        log.info("[%s] hit #%s %s", name, aid, data["title"][:48])
            if backfill > 0:
                # 每块提交回填指针，中断后可续跑
                store.set_state("backfilled_through:" + name, chunk[-1])
            if fetcher.dead:
                log.warning("[%s] circuit breaker open, stop at id %s", name, chunk[-1])
                scan_end = chunk[-1]
                break
            if not fetcher.budget_left():
                log.warning("[%s] request budget, stop at id %s", name, chunk[-1])
                scan_end = chunk[-1]
                break
        else:
            scan_end = chunk[-1]
        if backfill > 0:
            store.set_state("backfilled_through:" + name, lowest if lowest else scan_start)
        if last == 0:
            # 首次运行：本轮已覆盖 (scan_start, frontier]，直接推进到前沿
            store.set_state("scanned_through:" + name, frontier)
        elif backfill <= 0:
            store.set_state("scanned_through:" + name, max(scan_end, last))
    elif backfill > 0:
        log.info("[%s] no backfill range", name)

    # 播种 ID 每次运行复查（刷新截止日期等）
    if source.seed_ids:
        results = fetcher.get_many([source.detail_path(a) for a in source.seed_ids])
        for aid, r in zip(source.seed_ids, results):
            data = source.parse_response(r, aid)
            if data == "invalid" or not isinstance(data, dict):
                continue
            hits = match_hits(data, cfg)
            if not hits:
                hits = match_hits(_augmented(source, data), cfg)
            if hits:
                data["matched_keywords"] = hits
                if store.upsert(data):
                    found += 1
                    log.info("[%s] seed hit #%s %s", name, aid, data["title"][:48])

    if scan_start is not None:
        log.info("[%s] scanned [%d..%d] checked=%d found=%d",
                 name, scan_start, scan_end, checked, found)
    return found, checked


def _augmented(source, data):
    """标题含『海洋』但未命中时，来源可补充正文再匹配一次"""
    if not hasattr(source, "augment") or not isinstance(data, dict):
        return data
    if "海洋" not in data["title"] + data["content"]:
        return data
    extra = source.augment(data)
    if extra:
        merged = dict(data)
        merged["content"] = (data["content"] + " " + extra)[:6000]
        return merged
    return data
