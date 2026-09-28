# -*- coding: utf-8 -*-
"""HTTP 会话：线程本地连接、全局限速、重试"""
import time
import random
import logging
import threading
from concurrent.futures import ThreadPoolExecutor

import requests

log = logging.getLogger("collector")

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")


class Fetcher:
    """多线程安全：每线程独立 Session；全局按 min_interval 间隔发起请求"""

    def __init__(self, base, timeout=25, min_delay=0.4, max_delay=0.9,
                 max_requests=1200, workers=3, fail_limit=25):
        self.base = base.rstrip("/")
        self.timeout = timeout
        self.min_delay = min_delay
        self.max_delay = max_delay
        self.max_requests = max_requests
        self.workers = workers
        self.fail_limit = fail_limit
        self._n = 0
        self._n_lock = threading.Lock()
        self._slot_lock = threading.Lock()
        self._next_slot = 0.0
        self._fails = 0
        self.dead = False
        self._local = threading.local()

    @property
    def session(self):
        if not hasattr(self._local, "session"):
            s = requests.Session()
            s.headers.update({
                "User-Agent": UA,
                "Accept-Language": "zh-CN,zh;q=0.9",
            })
            self._local.session = s
        return self._local.session

    def _throttle(self):
        with self._slot_lock:
            now = time.monotonic()
            wait = self._next_slot - now
            self._next_slot = max(now, self._next_slot) + \
                random.uniform(self.min_delay, self.max_delay)
        if wait > 0:
            time.sleep(wait)

    def budget_left(self):
        with self._n_lock:
            return self._n < self.max_requests

    def get(self, path_or_url, **kw):
        if self.dead:
            return None
        with self._n_lock:
            if self._n >= self.max_requests:
                return None
            self._n += 1
        url = path_or_url if path_or_url.startswith("http") else self.base + path_or_url
        self._throttle()
        last = None
        for attempt in range(3):
            try:
                r = self.session.get(url, timeout=self.timeout, **kw)
                r.encoding = "utf-8"
                self._fails = 0
                return r
            except requests.RequestException as e:
                last = e
                time.sleep(1.5 * (attempt + 1))
        self._fails += 1
        log.warning("GET failed %s: %s", url, last)
        if self._fails >= self.fail_limit:
            self.dead = True
            log.error("circuit breaker open: %d consecutive failures, "
                      "domain likely blocked/unreachable", self._fails)
        return None

    def get_many(self, paths):
        """并发抓取（保持传入顺序返回），单请求仍受全局限速"""
        if not paths:
            return []
        with ThreadPoolExecutor(max_workers=self.workers) as ex:
            return list(ex.map(self.get, paths))
