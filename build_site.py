# -*- coding: utf-8 -*-
"""从 SQLite 生成静态站点：site/index.html + rss.xml + jobs.json"""
import io
import os
import re
import sys
import html
import json
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from collector.store import Store  # noqa: E402

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")


def esc(s):
    return html.escape(str(s or ""))


def classify(j):
    """单位性质分类（顺序敏感）"""
    t = (j.get("unit") or "") + " " + j["title"]
    if re.search(r"自然资源部|海洋局|海洋发展局|北海局|东海局|南海局|海区局|"
                 r"海洋环境监测|海洋预报|海洋信息|海洋技术|海洋档案馆|"
                 r"深海基地|极地研究|海洋中心|人民政府|人力资源和社会|人社局|"
                 r"管理局|服务中心|委员会", t):
        return "部委事业"
    if re.search(r"大学|学院|学校", t):
        return "高校"
    if re.search(r"研究所|研究院|实验室|研究中心|国家实验室", t):
        return "科研院所"
    if re.search(r"公司|集团|海油|中船|中交|中核|广核|电建|能建|石化|石油|"
                 r"航运|港口|疏浚|勘察|设计院", t):
        return "央企国企"
    return "其他"


SOURCE_LABELS = {"gaoxiaojob": "高校人才网", "sciencehr": "科学人才网"}


def extract_city(j):
    """从地点/标题/单位/摘要提取城市"""
    text = " ".join([j["location"] or "", j["title"], j["unit"] or "", j["summary"] or ""])
    for city in ("青岛", "北京", "上海", "天津", "重庆", "厦门", "大连", "广州", "深圳",
                 "杭州", "南京", "武汉", "成都", "舟山", "哈尔滨", "长春", "沈阳",
                 "西安", "郑州", "济南", "福州", "海口", "北海", "湛江", "烟台",
                 "威海", "三亚", "宁波", "苏州", "合肥", "长沙", "珠海", "兰州", "贵阳"):
        if city in text:
            return city
    return ""


def job_card(j):
    deadline = j["deadline"] or ""
    has_dl = bool(re.match(r"^20\d{2}-\d{2}-\d{2}$", deadline))
    cat = classify(j)
    loc = " · ".join(x for x in [j["province"], j["location"]] if x and x != j["province"]) \
        or j["province"] or ""
    summary = esc((j["summary"] or "")[:200])
    subjects = "".join('<span class="tag t-sub">%s</span>' % esc(s) for s in j["subjects"])
    kws = "".join('<span class="tag t-kw">%s</span>' % esc(k) for k in j["matched_keywords"][:4])
    src_label = SOURCE_LABELS.get(j.get("source"), j.get("source") or "")
    city = extract_city(j)
    return {
        "id": j["id"],
        "cat": cat,
        "province": j["province"] or "",
        "city": city,
        "degree": j["degree"] or "",
        "source": src_label,
        "deadline": deadline,
        "has_dl": has_dl,
        "publish": j["publish_date"] or "",
        "html": f"""<article class="card cat-{cat}" data-cat="{esc(cat)}"
    data-province="{esc(j['province'])}" data-city="{esc(city)}" data-degree="{esc(j['degree'])}"
    data-source="{esc(src_label)}" data-deadline="{esc(deadline)}"
    data-hasdl="{1 if has_dl else 0}" data-pub="{esc(j['publish_date'])}"
    data-text="{esc(j['title'])} {esc(j['unit'])} {esc(loc)} {esc(' '.join(j['subjects']))} {summary}">
  <div class="card-main">
    <a class="title" href="{esc(j['url'])}" target="_blank" rel="noopener">{esc(j['title'])}</a>
    <div class="meta">
      {f'<span class="m-unit">{esc(j["unit"])}</span>' if j['unit'] else ''}
      {f'<span class="m-loc">{esc(loc)}</span>' if loc else ''}
      {f'<span class="m-deg">{esc(j["degree"])}</span>' if j['degree'] else ''}
      {f'<span class="m-sal">{esc(j["salary"])}</span>' if j.get('salary') else ''}
    </div>
    <p class="summary">{summary}&hellip;</p>
    <div class="tags">{subjects}{kws}</div>
  </div>
  <div class="card-side">
    <span class="pill cat-pill">{esc(cat)}</span>
    <span class="dl" data-dl="{esc(deadline)}" data-hasdl="{1 if has_dl else 0}"></span>
    <span class="pub">发布 {esc(j['publish_date'] or '—')}</span>
    <span class="src">{esc(src_label)}</span>
  </div>
</article>"""
    }


def build_rss(jobs, built):
    items = []
    for j in jobs[:100]:
        desc = esc((j["summary"] or "")[:300])
        pub = ""
        if j["publish_date"]:
            try:
                d = datetime.strptime(j["publish_date"], "%Y-%m-%d")
                pub = d.strftime("%a, %d %b %Y 08:00:00 +0800")
            except ValueError:
                pass
        items.append(f"""    <item>
      <title>{esc(j['title'])}</title>
      <link>{esc(j['url'])}</link>
      <guid isPermaLink="true">{esc(j['url'])}</guid>
      <description>{desc}…（来源：{esc(SOURCE_LABELS.get(j['source'], j['source'] or ''))}）</description>
      <pubDate>{pub}</pubDate>
    </item>""")
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>海洋化学招聘信息聚合 · 2026</title>
    <link>https://example.github.io/ocean-chem-jobs/</link>
    <description>海洋化学学科招聘信息自动聚合（高校人才网 / 科学人才网）</description>
    <language>zh-CN</language>
    <pubDate>{built}</pubDate>
{chr(10).join(items)}
  </channel>
</rss>"""


PAGE = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>海洋化学招聘信息聚合 · 2026</title>
<style>
:root{{
  --navy:#0a4d6e; --blue:#0e6ba8; --teal:#0fb9b1;
  --bg:#f2f7fa; --card:#fff; --line:#e0ecf3;
  --text:#16324a; --muted:#5b7a8f;
  --ok:#0a7a3d; --warn:#c2620a; --bad:#b03030;
}}
*{{box-sizing:border-box;margin:0;padding:0}}
body{{font-family:"PingFang SC","Microsoft YaHei",system-ui,sans-serif;background:var(--bg);color:var(--text);line-height:1.6}}
a{{color:var(--blue)}}

/* ---------- hero ---------- */
.hero{{position:relative;background:linear-gradient(135deg,#073a56 0%,#0e6ba8 55%,#0fb9b1 130%);color:#fff;padding:46px 20px 66px;text-align:center;overflow:hidden}}
.hero::before{{content:"";position:absolute;inset:0;background:radial-gradient(1200px 400px at 80% -10%,rgba(255,255,255,.14),transparent 60%)}}
.hero h1{{font-size:clamp(20px,3.4vw,30px);letter-spacing:1px;position:relative}}
.hero p.sub{{margin-top:8px;font-size:13px;opacity:.82;position:relative}}
.stats{{display:flex;gap:12px;justify-content:center;margin-top:26px;flex-wrap:wrap;position:relative}}
.stat{{background:rgba(255,255,255,.13);border:1px solid rgba(255,255,255,.25);backdrop-filter:blur(6px);border-radius:12px;padding:10px 22px;min-width:120px}}
.stat b{{display:block;font-size:24px;font-weight:700}}
.stat-qd{{background:rgba(255,255,255,.22);border-color:rgba(255,255,255,.5)}}
.stat span{{font-size:12px;opacity:.85}}
.wave{{position:absolute;bottom:-1px;left:0;width:100%;line-height:0}}
.wave svg{{width:100%;height:36px;display:block}}

/* ---------- toolbar ---------- */
.wrap{{max-width:960px;margin:-28px auto 0;padding:0 16px 30px;position:relative;z-index:2}}
.toolbar{{background:#fff;border:1px solid var(--line);border-radius:14px;box-shadow:0 8px 24px rgba(10,77,110,.08);padding:12px;display:flex;gap:10px;flex-wrap:wrap;align-items:center;position:sticky;top:10px;z-index:10}}
.toolbar .search{{flex:1 1 220px;display:flex}}
.toolbar input[type=search]{{width:100%;padding:10px 14px;border:1px solid var(--line);border-radius:9px;font-size:14px;outline:none;background:#f8fbfd}}
.toolbar input[type=search]:focus{{border-color:var(--blue);background:#fff}}
.seg{{display:flex;border:1px solid var(--line);border-radius:9px;overflow:hidden}}
.seg button{{border:0;background:#f8fbfd;padding:9px 14px;font-size:13px;cursor:pointer;color:var(--muted)}}
.seg button.on{{background:var(--blue);color:#fff}}
.toolbar select{{padding:9px 10px;border:1px solid var(--line);border-radius:9px;font-size:13px;color:var(--text);background:#f8fbfd;cursor:pointer;outline:none}}
.chips{{display:flex;gap:8px;margin:14px 2px 4px;flex-wrap:wrap;align-items:center}}
.chip{{border:1px solid var(--line);background:#fff;border-radius:999px;padding:5px 14px;font-size:12.5px;cursor:pointer;color:var(--muted);transition:.15s}}
.chip.on{{background:var(--navy);border-color:var(--navy);color:#fff}}
.count{{font-size:12.5px;color:var(--muted);margin:8px 2px 12px}}

/* ---------- cards ---------- */
.card{{background:var(--card);border:1px solid var(--line);border-left:4px solid var(--blue);border-radius:12px;padding:16px 18px;margin-bottom:13px;display:flex;gap:16px;justify-content:space-between;transition:.18s}}
.card:hover{{box-shadow:0 10px 26px rgba(10,77,110,.13);transform:translateY(-2px)}}
.card.cat-高校{{border-left-color:var(--blue)}}
.card.cat-科研院所{{border-left-color:var(--teal)}}
.card.cat-部委事业{{border-left-color:#7c5cbf}}
.card.cat-央企国企{{border-left-color:#e8a33d}}
.card.cat-其他{{border-left-color:#8a9bb0}}
.card.hide{{display:none}}
.card-main{{flex:1;min-width:0}}
.title{{font-size:15.5px;font-weight:650;color:var(--navy);text-decoration:none;word-break:break-all}}
.title:hover{{text-decoration:underline}}
.meta{{margin-top:7px;font-size:12.8px;color:var(--muted);display:flex;gap:14px;flex-wrap:wrap}}
.meta .m-unit{{color:#33566e;font-weight:550}}
.summary{{font-size:13px;color:#41586b;margin-top:8px;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}}
.tags{{margin-top:9px}}
.tag{{display:inline-block;font-size:11.5px;border-radius:999px;padding:2px 10px;margin:3px 5px 0 0}}
.t-sub{{background:#e7f1f8;color:var(--blue)}}
.t-kw{{background:#e9f7ee;color:var(--ok)}}
.card-side{{flex:0 0 118px;display:flex;flex-direction:column;align-items:flex-end;gap:7px;font-size:12px;color:var(--muted)}}
.pill{{border-radius:999px;padding:2px 11px;font-size:11.5px}}
.cat-pill{{background:#eef3f7;color:#4a6478}}
.dl{{font-weight:650;font-size:12.5px}}
.dl.open{{color:var(--ok)}}
.dl.soon{{color:var(--warn)}}
.dl.past{{color:var(--bad)}}
.dl.na{{color:var(--muted);font-weight:400}}
.pub,.src{{font-size:11.5px}}
.new-badge{{display:inline-block;background:#0fb9b1;color:#fff;border-radius:999px;font-size:10.5px;padding:1px 8px;margin-left:8px;vertical-align:2px}}

.empty{{text-align:center;color:var(--muted);padding:60px 0;display:none}}
footer{{text-align:center;font-size:12px;color:#8ba0b0;padding:26px 16px 46px;line-height:1.9}}
footer a{{color:#6d8fa5}}

@media (max-width:640px){{
  .card{{flex-direction:column}}
  .card-side{{flex-direction:row;flex-wrap:wrap;align-items:center;gap:10px}}
}}
</style>
</head>
<body>

<header class="hero">
  <h1>海洋化学招聘信息聚合 · 2026</h1>
  <p class="sub">自动聚合高校人才网 / 科学人才网公开信息 · 每日更新 · 以各单位官方公告为准</p>
  <div class="stats">
    <div class="stat"><b>{total}</b><span>岗位总数</span></div>
    <div class="stat"><b>{week_new}</b><span>本周新增</span></div>
    <div class="stat"><b>{open_n}</b><span>报名中</span></div>
    <div class="stat"><b>{soon_n}</b><span>7天内截止</span></div>
    <div class="stat stat-qd"><b>{qd_n}</b><span>青岛在招</span></div>
  </div>
  <div class="wave"><svg viewBox="0 0 1440 36" preserveAspectRatio="none"><path d="M0,20 C240,40 480,0 720,16 C960,32 1200,8 1440,20 L1440,36 L0,36 Z" fill="#f2f7fa"></path></svg></div>
</header>

<div class="wrap">
  <div class="toolbar">
    <div class="search"><input id="q" type="search" placeholder="搜索：方向 / 单位 / 地点 / 关键词…"></div>
    <div class="seg" id="status">
      <button data-v="all" class="on">全部</button>
      <button data-v="open">报名中</button>
      <button data-v="expired">已截止</button>
    </div>
    <select id="city"><option value="">全部城市</option>{city_opts}</select>
    <select id="province"><option value="">全部省份</option>{prov_opts}</select>
    <select id="degree"><option value="">全部学历</option>{deg_opts}</select>
    <select id="source"><option value="">全部来源</option>{src_opts}</select>
    <select id="sort">
      <option value="pub">最新发布</option>
      <option value="deadline">截止临近</option>
    </select>
  </div>

  <div class="chips" id="cats">
    <button class="chip on" data-v="">全部类型</button>
    <button class="chip" data-v="高校">高校</button>
    <button class="chip" data-v="科研院所">科研院所</button>
    <button class="chip" data-v="部委事业">部委/海洋局系统</button>
    <button class="chip" data-v="央企国企">央企国企</button>
    <button class="chip" data-v="其他">其他</button>
  </div>

  <div class="count" id="count"></div>
  <div id="list">{cards}</div>
  <div class="empty" id="empty">没有符合条件的招聘信息</div>
</div>

<footer>
  数据由程序自动采集自 <a href="https://www.gaoxiaojob.com" target="_blank" rel="noopener">高校人才网</a> 与
  <a href="https://www.sciencehr.net" target="_blank" rel="noopener">科学人才网</a> 公开页面，仅作学科信息聚合，具体以各单位官方公告为准。<br>
  共 {total} 条 · 构建 {built} ·
  <a href="rss.xml">RSS 订阅</a> · <a href="jobs.json">JSON 数据</a>
</footer>

<script>
const today = new Date('{today}');
const cards = Array.from(document.querySelectorAll('.card'));

// 截止状态渲染
cards.forEach(c => {{
  const el = c.querySelector('.dl');
  const dl = el.dataset.dl, has = el.dataset.hasdl === '1';
  if (!has) {{ el.textContent = '长期/详见正文'; el.classList.add('na'); return; }}
  const d = new Date(dl);
  const days = Math.round((d - today) / 864e5);
  c.dataset.expired = days < 0 ? '1' : '0';
  if (days < 0) {{ el.textContent = '已截止 ' + dl; el.classList.add('past'); }}
  else if (days <= 7) {{ el.textContent = days === 0 ? '今日截止' : '剩 ' + days + ' 天'; el.classList.add('soon'); }}
  else {{ el.textContent = '截止 ' + dl; el.classList.add('open'); }}
  if (days >= 0 && days <= 7) {{ el.classList.add('open'); }}
}});
// NEW 徽章（7 天内发布）
cards.forEach(c => {{
  const pub = c.dataset.pub;
  if (!pub) return;
  const days = Math.round((new Date(pub) - today) / 864e5);
  if (days <= 7) {{
    const t = c.querySelector('.title');
    const b = document.createElement('span');
    b.className = 'new-badge'; b.textContent = 'NEW';
    t.after(b);
  }}
}});

const q = document.getElementById('q');
const provSel = document.getElementById('province');
const citySel = document.getElementById('city');
const degSel = document.getElementById('degree');
const srcSel = document.getElementById('source');
const sortSel = document.getElementById('sort');
const countEl = document.getElementById('count');
const emptyEl = document.getElementById('empty');
const listEl = document.getElementById('list');
let status = 'all', cat = '';

function apply() {{
  const kw = q.value.trim().toLowerCase();
  let shown = cards.filter(c => {{
    if (kw && !c.dataset.text.toLowerCase().includes(kw)) return false;
    if (cat && c.dataset.cat !== cat) return false;
    if (citySel.value && c.dataset.city !== citySel.value) return false;
    if (provSel.value && c.dataset.province !== provSel.value) return false;
    if (degSel.value && c.dataset.degree !== degSel.value) return false;
    if (srcSel.value && c.dataset.source !== srcSel.value) return false;
    if (status === 'open' && c.dataset.expired === '1') return false;
    if (status === 'expired' && c.dataset.expired !== '1') return false;
    return true;
  }});
  if (sortSel.value === 'deadline') {{
    shown.sort((a, b) => (a.dataset.hasdl === '1' ? a.dataset.deadline : '9999')
      .localeCompare(b.dataset.hasdl === '1' ? b.dataset.deadline : '9999'));
  }}
  cards.forEach(c => c.classList.add('hide'));
  shown.forEach(c => c.classList.remove('hide'));
  countEl.textContent = '共 ' + shown.length + ' 条';
  emptyEl.style.display = shown.length ? 'none' : 'block';
}}

q.addEventListener('input', apply);
[provSel, citySel, degSel, srcSel, sortSel].forEach(s => s.addEventListener('change', apply));
document.getElementById('status').addEventListener('click', e => {{
  if (e.target.tagName !== 'BUTTON') return;
  document.querySelectorAll('#status button').forEach(b => b.classList.remove('on'));
  e.target.classList.add('on');
  status = e.target.dataset.v;
  apply();
}});
document.getElementById('cats').addEventListener('click', e => {{
  if (e.target.tagName !== 'BUTTON') return;
  document.querySelectorAll('#cats .chip').forEach(b => b.classList.remove('on'));
  e.target.classList.add('on');
  cat = e.target.dataset.v;
  apply();
}});
apply();
</script>
</body>
</html>"""


def main():
    base = os.path.dirname(os.path.abspath(__file__))
    jobs = Store(os.path.join(base, "data", "jobs.db")).all_jobs()
    today = datetime.now().strftime("%Y-%m-%d")
    built = datetime.now().strftime("%Y-%m-%d %H:%M")

    week_ago = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
    week_new = sum(1 for j in jobs if (j["first_seen"] or "")[:10] >= week_ago)

    def is_open(j):
        dl = j["deadline"]
        return not (re.match(r"^20\d{2}-\d{2}-\d{2}$", dl or "") and dl < today)

    open_n = sum(1 for j in jobs if is_open(j))
    soon_n = sum(1 for j in jobs
                 if j["deadline"] and re.match(r"^20\d{2}-\d{2}-\d{2}$", j["deadline"])
                 and today <= j["deadline"] <= (datetime.now() + timedelta(days=7)).strftime("%Y-%m-%d"))

    provinces = sorted({j["province"] for j in jobs if j["province"]})
    degrees = sorted({j["degree"] for j in jobs if j["degree"]})
    sources = sorted({SOURCE_LABELS.get(j["source"], j["source"] or "")
                      for j in jobs if j["source"]})
    cities = sorted({c for c in (extract_city(j) for j in jobs) if c})
    qd_n = sum(1 for j in jobs if extract_city(j) == "青岛")

    cards = "".join(job_card(j)["html"] for j in jobs)
    page = PAGE.format(
        cards=cards,
        total=len(jobs),
        week_new=week_new,
        open_n=open_n,
        soon_n=soon_n,
        qd_n=qd_n,
        prov_opts="".join('<option>%s</option>' % esc(p) for p in provinces),
        deg_opts="".join('<option>%s</option>' % esc(d) for d in degrees),
        src_opts="".join('<option>%s</option>' % esc(s) for s in sources),
        city_opts="".join('<option>%s</option>' % esc(c) for c in cities),
        built=built,
        today=today,
    )

    out_dir = os.path.join(base, "site")
    os.makedirs(out_dir, exist_ok=True)
    with open(os.path.join(out_dir, "index.html"), "w", encoding="utf-8") as f:
        f.write(page)
    with open(os.path.join(out_dir, "rss.xml"), "w", encoding="utf-8") as f:
        f.write(build_rss(jobs, built))
    with open(os.path.join(out_dir, "jobs.json"), "w", encoding="utf-8") as f:
        json.dump(jobs, f, ensure_ascii=False, indent=1)
    print("site built: site/index.html (%d jobs) + rss.xml + jobs.json" % len(jobs))


if __name__ == "__main__":
    main()
