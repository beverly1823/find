# -*- coding: utf-8 -*-
"""SQLite 存储 + 去重（多来源）"""
import json
import re
import sqlite3
from datetime import datetime

SCHEMA = """
CREATE TABLE IF NOT EXISTS jobs (
    id INTEGER PRIMARY KEY,
    source TEXT,
    title TEXT NOT NULL,
    norm_title TEXT,
    url TEXT NOT NULL,
    unit TEXT,
    province TEXT,
    location TEXT,
    publish_date TEXT,
    deadline TEXT,
    degree TEXT,
    subjects TEXT,
    apply_method TEXT,
    salary TEXT,
    summary TEXT,
    matched_keywords TEXT,
    first_seen TEXT,
    updated_at TEXT
);
CREATE TABLE IF NOT EXISTS state (
    key TEXT PRIMARY KEY,
    value TEXT
);
CREATE INDEX IF NOT EXISTS idx_jobs_norm ON jobs(norm_title);
"""

FIELDS = ["id", "source", "title", "url", "unit", "province", "location",
          "publish_date", "deadline", "degree", "subjects", "apply_method",
          "salary", "summary", "matched_keywords", "first_seen"]


class Store:
    def __init__(self, path):
        self.conn = sqlite3.connect(path, timeout=30)
        self.conn.execute("PRAGMA busy_timeout=30000")
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.executescript(SCHEMA)
        self._migrate()
        self.conn.commit()

    def _migrate(self):
        cols = [r[1] for r in self.conn.execute("PRAGMA table_info(jobs)")]
        if cols and "source" not in cols:
            self.conn.execute(
                "ALTER TABLE jobs ADD COLUMN source TEXT DEFAULT 'gaoxiaojob'")
        if cols and "salary" not in cols:
            self.conn.execute(
                "ALTER TABLE jobs ADD COLUMN salary TEXT DEFAULT ''")
        # 旧版全局状态键 -> 按来源键
        for old, new in [("scanned_through", "scanned_through:gaoxiaojob"),
                         ("backfilled_through", "backfilled_through:gaoxiaojob")]:
            row = self.conn.execute(
                "SELECT value FROM state WHERE key=?", (old,)).fetchone()
            if row and not self.conn.execute(
                    "SELECT 1 FROM state WHERE key=?", (new,)).fetchone():
                self.conn.execute(
                    "INSERT INTO state(key,value) VALUES(?,?)", (new, row[0]))

    def get_state(self, key, default=None):
        row = self.conn.execute("SELECT value FROM state WHERE key=?", (key,)).fetchone()
        return row[0] if row else default

    def set_state(self, key, value):
        self.conn.execute(
            "INSERT OR REPLACE INTO state(key,value) VALUES(?,?)", (key, str(value)))
        self.conn.commit()

    def has_job(self, job_id):
        return self.conn.execute(
            "SELECT 1 FROM jobs WHERE id=?", (job_id,)).fetchone() is not None

    def upsert(self, job):
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        norm = re.sub(r"[\s（）()【】\[\]·、，,\-—]", "", job["title"])
        dup = self.conn.execute(
            "SELECT id FROM jobs WHERE norm_title=? AND (source=? OR ?='')",
            (norm, job.get("source") or "", job.get("source") or "")).fetchone()
        if dup:
            return False
        self.conn.execute(
            """INSERT OR REPLACE INTO jobs
               (id,source,title,norm_title,url,unit,province,location,publish_date,
                deadline,degree,subjects,apply_method,salary,summary,matched_keywords,
                first_seen,updated_at)
               VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (job["id"], job.get("source"), job["title"], norm, job["url"],
             job.get("unit"), job.get("province"), job.get("location"),
             job.get("publish_date"), job.get("deadline"), job.get("degree"),
             json.dumps(job.get("subjects", []), ensure_ascii=False),
             job.get("apply_method"), job.get("salary", ""),
             (job.get("summary") or job.get("content", ""))[:160],
             json.dumps(job.get("matched_keywords", []), ensure_ascii=False),
             now, now))
        self.conn.commit()
        return True

    def all_jobs(self):
        cur = self.conn.execute(
            """SELECT id,source,title,url,unit,province,location,publish_date,deadline,
                      degree,subjects,apply_method,salary,summary,matched_keywords,first_seen
               FROM jobs ORDER BY publish_date DESC, id DESC""")
        out = []
        for row in cur:
            d = dict(zip(FIELDS, row))
            d["subjects"] = json.loads(d["subjects"] or "[]")
            d["matched_keywords"] = json.loads(d["matched_keywords"] or "[]")
            out.append(d)
        return out
