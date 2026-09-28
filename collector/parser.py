# -*- coding: utf-8 -*-
"""详情页解析：高校人才网 / 科学人才网 + 关键词匹配"""
import re

from bs4 import BeautifulSoup

_YEAR = re.compile(r"20\d{2}")


# ---------- 高校人才网 ----------

def parse_gaoxiaojob(html):
    soup = BeautifulSoup(html, "lxml")
    h1 = soup.find("h1")
    if not h1:
        return None
    title = h1.get_text(" ", strip=True)

    meta_box = soup.select_one("ul.detail-content")
    meta = _parse_meta(meta_box) if meta_box else {}
    subjects = meta.pop("_subjects", [])

    content_el = soup.select_one("div.section-main")
    content = content_el.get_text(" ", strip=True) if content_el else ""

    return _finish({
        "title": title,
        "publish_date": meta.get("发布时间", ""),
        "deadline": meta.get("截止日期", ""),
        "degree": meta.get("学历要求", ""),
        "province": meta.get("所属省份", ""),
        "location": meta.get("工作地点", ""),
        "apply_method": meta.get("报名方式", ""),
        "subjects": subjects,
        "content": content[:6000],
        "salary": "",
    })


def _parse_meta(box):
    """逐文本节点解析 '标签：值' / '标签：'+下一行值 / 需求学科链接"""
    meta = {}
    subjects = []
    last_label = None
    in_subjects = False
    for el in box.descendants:
        if getattr(el, "name", None) not in (None, "li", "a", "span", "div"):
            continue
        text = (el.string or "").strip() if getattr(el, "string", None) else None
        if not text:
            continue
        if "：" in text or ":" in text:
            parts = re.split(r"[:：]", text, maxsplit=1)
            label = parts[0].strip()
            val = parts[1].strip() if len(parts) > 1 else ""
            if label == "需求学科":
                in_subjects = True
                last_label = label
                continue
            if label in ("发布时间", "截止日期", "学历要求", "所属省份",
                         "工作地点", "报名方式", "栏目分类"):
                meta[label] = val
                in_subjects = False
                last_label = label
                continue
        if in_subjects and getattr(el, "name", None) == "a":
            if re.match(r"^/column/\d+\.html$", el.get("href", "")):
                subjects.append(text)
            continue
        if last_label in ("所属省份", "工作地点") and not meta.get(last_label):
            meta[last_label] = text
    meta["_subjects"] = subjects
    return meta


# ---------- 科学人才网 ----------

def parse_sciencehr(html):
    soup = BeautifulSoup(html, "lxml")
    h1 = soup.select_one("h1.job_details_name")
    title_tag = soup.title.string.strip() if soup.title and soup.title.string else ""
    if not h1 or not title_tag:
        return None

    job_name = h1.get_text(" ", strip=True)
    # title-tag 格式：{单位}{岗位名}招聘 - 科学人才网
    core = re.sub(r"\s*-\s*科学人才网\s*$", "", title_tag)
    unit = None
    if job_name and job_name in core:
        head = core[:core.find(job_name)]
        head = head.rstrip("招聘").rstrip()
        unit = head if len(head) >= 4 else None
    title = core if core.endswith("招聘") else (job_name + "招聘")

    meta_box = soup.select_one("div.job_ceil")
    meta_text = meta_box.get_text(" ", strip=True) if meta_box else ""
    parts = re.split(r"[｜|]", meta_text)
    parts = [p.strip() for p in parts if p.strip()]

    salary = parts[0] if parts and "面议" in parts[0] else ""
    location = parts[1] if len(parts) > 1 else ""
    degree = next((p for p in parts if "学历" in p), "")
    m_pub = re.search(r"(20\d{2}[-/.年]\d{1,2}[-/.月]\d{1,2})\s*发布", meta_text)
    publish_date = _norm_date(m_pub.group(1)) if m_pub else ""

    desc = soup.select_one("div.job_details_describe")
    content = desc.get_text(" ", strip=True) if desc else ""

    m_dl = re.search(r"(?:报名截止|截止时间|截止日期|投递截止)[^\d]{0,4}(20\d{2}[-/.年]\d{1,2}[-/.月]\d{1,2})",
                     content)
    deadline = _norm_date(m_dl.group(1)) if m_dl else ""

    return _finish({
        "title": title,
        "publish_date": publish_date,
        "deadline": deadline,
        "degree": degree.replace("学历", "").strip(),
        "province": "",
        "location": location,
        "apply_method": "在线投递",
        "subjects": [],
        "content": content[:6000],
        "salary": salary,
        "unit": unit,
        "job_name": job_name,
    })


def _norm_date(s):
    s = s.replace("年", "-").replace("月", "-").replace("日", "").replace("/", "-").replace(".", "-")
    m = re.match(r"(\d{4})-(\d{1,2})-(\d{1,2})", s)
    if not m:
        return ""
    return "%s-%02d-%02d" % (m.group(1), int(m.group(2)), int(m.group(3)))


# ---------- 事业单位招聘网 ----------

def parse_shiyebian(html):
    soup = BeautifulSoup(html, "lxml")
    h1 = soup.find("h1")
    if not h1:
        return None
    title = h1.get_text(" ", strip=True)

    box = h1.parent  # div.card-content
    box_text = box.get_text("\n", strip=True) if box else ""
    m_pub = re.search(r"发布时间[:：]\s*(20\d{2})[-/年](\d{1,2})[-/月](\d{1,2})", box_text)
    publish_date = ("%s-%02d-%02d" % (m_pub.group(1), int(m_pub.group(2)),
                                      int(m_pub.group(3)))) if m_pub else ""

    body = soup.select_one("div.zhengwen")
    content = body.get_text(" ", strip=True) if body else ""

    m_dl = None
    for pat in (r"(?:报名截止|截止报名|报名[^。]{0,8}截止)[^\d]{0,3}(20\d{2})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})",
                r"(?:发布之日起至|发布之时起至)[^\d]{0,4}(20\d{2})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})",
                r"报名(?:时间|日期|及材料)?[^。\d]{0,24}(20\d{2})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日"):
        m_dl = re.search(pat, content)
        if m_dl:
            break
    deadline = ("%s-%02d-%02d" % (m_dl.group(1), int(m_dl.group(2)),
                                  int(m_dl.group(3)))) if m_dl else ""

    return _finish({
        "title": title,
        "publish_date": publish_date,
        "deadline": deadline,
        "degree": "",
        "province": "",
        "location": "",
        "apply_method": "",
        "subjects": [],
        "content": content[:6000],
        "salary": "",
    })


def _finish(data):
    """统一补齐派生字段"""
    title = data["title"]
    if not data.get("unit"):
        data["unit"] = guess_unit(title)
    return data


# ---------- 高校人才网职位页（m 站） ----------

def parse_gaoxiaojob_job(html):
    soup = BeautifulSoup(html, "lxml")
    header = soup.select_one("header.job-header")
    if not header:
        return None
    h1 = soup.find("h1")
    job_name = h1.get_text(" ", strip=True) if h1 else ""

    text = header.get_text("\n", strip=True)
    lines = [l.strip() for l in text.split("\n") if l.strip()]

    m_pub = re.search(r"(20\d{2}-\d{2}-\d{2})\s*发布", text)
    publish_date = m_pub.group(1) if m_pub else ""

    m_deadline = re.search(r"截止日期[:：]\s*([^\n]+)", text)
    deadline = m_deadline.group(1).strip() if m_deadline else ""

    # 需求专业：标签行或展开后的下一行
    major = ""
    for i, l in enumerate(lines):
        if "需求专业" in l:
            rest = re.sub(r"^.*需求专业[^：]*[:：]?", "", l).strip()
            if rest:
                major = rest
            elif i + 1 < len(lines):
                major = lines[i + 1]
            break

    # 公告标题：最长且含招聘字样的行
    anno_title = ""
    for l in lines:
        if len(l) > len(anno_title) and re.search(r"招聘|启事|公告|引进|信息", l):
            anno_title = l
    # 薪资：薪资样式行
    salary = ""
    for l in lines:
        if l != job_name and re.match(r"^[\d\-.万/年月kK元至-]+$", l) \
                and re.search(r"万|面议|元|k", l) and l != "面议":
            salary = l
            break
        if l == "面议":
            salary = "面议"
            break

    m_deg = re.search(r"(博士研究生|硕士研究生|本科|硕士|博士)", text)
    degree = m_deg.group(1) if m_deg else ""

    location = ""
    m_loc = re.search(r"\n(青岛|北京|上海|天津|重庆|厦门|大连|广州|深圳|杭州|南京|武汉|成都|舟山|"
                      r"哈尔滨|长春|沈阳|西安|郑州|济南|福州|海口|北海|湛江|烟台|威海|三亚|"
                      r"昆山|宁波|苏州|无锡|合肥|长沙|广州|珠海)\n", text)
    if m_loc:
        location = m_loc.group(1)

    a_anno = soup.select_one('a[href*="/announcement/detail/"]')
    anno_url = a_anno.get("href", "") if a_anno else ""

    content_el = soup.select_one("[class*=job-details], .job-content, article")
    content = content_el.get_text(" ", strip=True) if content_el else ""
    if not content:
        main = soup.select_one("main, .content, #app")
        content = main.get_text(" ", strip=True) if main else ""

    return _finish({
        "title": "%s（%s）" % (job_name, anno_title[:60]) if anno_title else job_name,
        "job_name": job_name,
        "publish_date": publish_date,
        "deadline": deadline,
        "degree": degree,
        "province": "",
        "location": location,
        "apply_method": "",
        "subjects": [major] if major else [],
        "major": major,
        "content": content[:5000],
        "salary": salary,
        "unit": anno_title and guess_unit(anno_title) or None,
    })


# ---------- 单位名推断 / 匹配 ----------

_TITLE_TAIL = re.compile(r"(招聘|选聘|考核|考试|公开|引进|招募|延揽)")


def guess_unit(title):
    """两种常见格式：
    1) 单位在前：中国海洋大学2026年诚聘… → 年份之前
    2) 年份在前：2025年中国海洋大学XX学部派遣制招聘公告 → 年份之后到动作词之前
    """
    m = _YEAR.search(title)
    if not m:
        return None
    if m.start() > 1:
        unit = title[:m.start()]
        unit = unit.rstrip("（( ,，-")
        return unit if len(unit) >= 4 else None
    after = title[m.end():].lstrip("年 ")
    if after.startswith("度"):
        after = after[1:].lstrip()
    m2 = _TITLE_TAIL.search(after)
    if m2 and m2.start() >= 4:
        unit = after[:m2.start()]
        unit = unit.rstrip("（( ，,·-面向")
        return unit if len(unit) >= 4 else None
    return None


def match_hits(data, cfg):
    """标题+正文多规则匹配；返回命中列表"""
    title = data["title"]
    content = data["content"]
    text = title + " " + content
    hits = [kw for kw in cfg["keywords_core"] if kw in text]

    for combo in _as_list(cfg.get("subject_combo")):
        if combo["subject"] in data["subjects"] \
                and any(w in text for w in combo["words"]):
            hits.append(combo["subject"] + "+组合")

    for combo in _as_list(cfg.get("org_combo")):
        org_hit = any(o in title for o in combo["orgs"])
        if org_hit and any(w in content for w in combo["words"]):
            hits.append("机构+化学")

    # 海洋系统单位：标题含单位词 → 直接收录（单位业务即涉海）
    for w in cfg.get("ocean_org_words", []):
        if w in title:
            hits.append("海洋系统单位")
            break

    # 央企国企：直接名单 或 名单+海洋语境词
    soe = cfg.get("soe_rules", {})
    if any(w in title for w in soe.get("direct", [])):
        hits.append("海洋央企国企")
    else:
        orgs = soe.get("with_ocean", {}).get("orgs", [])
        ocean_words = soe.get("with_ocean", {}).get("ocean", [])
        if any(o in title for o in orgs) \
                and any(o in text for o in ocean_words):
            hits.append("海洋央企国企")

    # 职位级专业匹配：需求专业含化学类 且 岗位语境涉海
    major = data.get("major", "") or ""
    marine_ctx = any(w in text for w in ("海洋", "海水", "海洋科学", "海洋生物", "海工", "海上"))
    if marine_ctx and any(k in major for k in ("化学", "海洋科学", "地球化学")):
        hits.append("专业:" + ("海洋科学" if "海洋科学" in major else "化学"))

    return sorted(set(hits))


def _as_list(x):
    if isinstance(x, dict):
        return [x]
    return x or []
