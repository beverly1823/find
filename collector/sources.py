# -*- coding: utf-8 -*-
"""招聘信息来源抽象：高校人才网 + 科学人才网"""
import re
import logging

from bs4 import BeautifulSoup

from .parser import parse_gaoxiaojob, parse_sciencehr, parse_shiyebian, parse_gaoxiaojob_job

log = logging.getLogger("collector")


class GaoxiaojobSource:
    """高校人才网：公告详情页 ID 递增，栏目页侧栏可发现前沿"""
    name = "gaoxiaojob"
    label = "高校人才网"

    def __init__(self, fetcher, cfg):
        self.fetcher = fetcher
        self.cfg = cfg
        self.frontier_columns = cfg.get("frontier_columns", [])
        self.seed_ids = cfg.get("seed_ids", [])

    def detail_path(self, aid):
        return "/announcement/detail/%d.html" % aid

    def discover_frontier(self, hint=0):
        frontier = 0
        for col in self.frontier_columns:
            r = self.fetcher.get(col)
            if r and r.status_code == 200:
                for m in re.finditer(r"/announcement/detail/(\d+)\.html", r.text):
                    frontier = max(frontier, int(m.group(1)))
        return frontier

    def parse_response(self, r, aid):
        if not r or r.status_code != 200:
            return "invalid"
        data = parse_gaoxiaojob(r.text)
        if not data:
            return "invalid"
        data["id"] = aid
        data["source"] = self.name
        data["source_label"] = self.label
        data["url"] = self.fetcher.base + "/announcement/detail/%d.html" % aid
        return data

    def augment(self, data):
        """总公告的岗位明细在职位列表子页里"""
        r = self.fetcher.get("/announcement/job-list?id=%d" % data["id"])
        if not r or r.status_code != 200:
            return None
        soup = BeautifulSoup(r.text, "lxml")
        rows = [tr.get_text(" ", strip=True) for tr in soup.select("tr")]
        return " ".join(t for t in rows if t)[:3000]


class SciencehrSource:
    """科学人才网：职位详情 /job/{id}.html 开放（PC 列表页有 WAF）。
    前沿用上探+二分发现，死 ID 返回小体积提示页"""
    name = "sciencehr"
    label = "科学人才网"

    def __init__(self, fetcher, cfg):
        self.fetcher = fetcher
        self.cfg = cfg
        self.seed_ids = cfg.get("seed_ids", [])

    def detail_path(self, aid):
        return "/job/%d.html" % aid

    def _is_valid(self, aid):
        r = self.fetcher.get(self.detail_path(aid))
        if not r or r.status_code != 200:
            return False
        return "提示信息" not in (r.text[:2000] or "") and len(r.text) > 5000

    def discover_frontier(self, hint=0):
        base = hint or (self.seed_ids[0] if self.seed_ids else 0)
        if not base:
            return 0
        if not self._is_valid(base):
            while base > 1000 and not self._is_valid(base):
                base -= 512
            if not self._is_valid(base):
                return 0
        lo = hi = base
        step = 256
        probes = 0
        while probes < 24:
            nxt = hi + step
            if self._is_valid(nxt):
                lo = hi = nxt
                step *= 2
                probes += 1
            else:
                break
        if hi == lo:
            return lo
        while hi - lo > 1 and probes < 40:
            mid = (lo + hi) // 2
            if self._is_valid(mid):
                lo = mid
            else:
                hi = mid
            probes += 1
        return lo

    def parse_response(self, r, aid):
        if not r or r.status_code != 200:
            return "invalid"
        if "提示信息" in (r.text[:2000] or "") or len(r.text) < 5000:
            return "invalid"
        data = parse_sciencehr(r.text)
        if not data:
            return "invalid"
        data["id"] = aid
        data["source"] = self.name
        data["source_label"] = self.label
        data["url"] = self.fetcher.base + "/job/%d.html" % aid
        return data


class ShiyebianSource:
    """事业单位招聘网 shiyebian.net：纯静态，文章 /xinxi/{id}.html ID 递增，
    404 表示无效。全国事业编/国企/部委单位公告聚合"""
    name = "shiyebian"
    label = "事业单位招聘网"

    def __init__(self, fetcher, cfg):
        self.fetcher = fetcher
        self.cfg = cfg
        self.seed_ids = cfg.get("seed_ids", [])

    def detail_path(self, aid):
        return "/xinxi/%d.html" % aid

    def discover_frontier(self, hint=0):
        # 最新列表页第一屏的文章 ID 即前沿
        r = self.fetcher.get("/xinxi/")
        if not r or r.status_code != 200:
            return 0
        frontier = 0
        for m in re.finditer(r"/xinxi/(\d+)\.html", r.text):
            frontier = max(frontier, int(m.group(1)))
        return frontier

    def parse_response(self, r, aid):
        if not r or r.status_code != 200 or len(r.text) < 5000:
            return "invalid"
        r.encoding = "gbk"   # 该站为 GBK 编码，覆盖 fetcher 默认 utf-8
        data = parse_shiyebian(r.text)
        if not data:
            return "invalid"
        data["id"] = aid
        data["source"] = self.name
        data["source_label"] = self.label
        data["url"] = self.fetcher.base + "/xinxi/%d.html" % aid
        return data


class GaoxiaojobJobSource:
    """高校人才网职位页（m.gaoxiaojob.com/job/detail/{id}.html）：
    职位级数据（公告拆分的具体岗位），带需求专业/地点/薪资，是化学岗位金标准。
    m 站开放、ID 递增但跳跃大（职位密度 ~5-10%）"""
    name = "gaoxiaojob_job"
    label = "高校人才网·职位"

    def __init__(self, fetcher, cfg):
        self.fetcher = fetcher
        self.cfg = cfg
        self.seed_ids = cfg.get("seed_ids", [])

    def detail_path(self, aid):
        return "/job/detail/%d.html" % aid

    def discover_frontier(self, hint=0):
        r = self.fetcher.get("/job/")
        if not r or r.status_code != 200:
            return hint or 0
        ids = [int(x) for x in re.findall(r"/job/detail/(\d+)\.html", r.text)]
        return max(ids) if ids else (hint or 0)

    def parse_response(self, r, aid):
        if not r or r.status_code != 200:
            return "invalid"
        data = parse_gaoxiaojob_job(r.text)
        if not data:
            return "invalid"   # 404 通用页无 job-header
        data["id"] = aid
        data["source"] = self.name
        data["source_label"] = self.label
        data["url"] = "https://m.gaoxiaojob.com/job/detail/%d.html" % aid
        return data


SOURCE_TYPES = {"gaoxiaojob": GaoxiaojobSource, "sciencehr": SciencehrSource,
                "shiyebian": ShiyebianSource, "gaoxiaojob_job": GaoxiaojobJobSource}
