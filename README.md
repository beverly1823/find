# 海洋化学招聘信息聚合（2026）

自动采集、聚合、发布海洋化学相关学科招聘信息的静态网站项目。

## 架构

```
config.yaml          关键词、来源、扫描参数
run_collect.py       采集入口（多来源增量 / 回填）
run_backfill.ps1     全量历史回填脚本（后台跑）
collector/
  fetcher.py         HTTP 会话（限速、重试、并发）
  sources.py         来源抽象：高校人才网 / 科学人才网
  parser.py          详情页字段解析 + 多规则匹配
  store.py           SQLite 存储 + 标题去重
build_site.py        生成 site/（index.html + rss.xml + jobs.json）
data/jobs.db         数据库
.github/workflows/collect.yml   每日 08:30 自动采集并发布
```

## 采集原理

**高校人才网**：公告详情页服务端渲染、无需登录、robots.txt 允许抓取，公告 ID
连续递增。从「高校招聘 / 海洋科学 / 化学」栏目页发现最新 ID（前沿），增量扫描
新 ID 段；标题含「海洋」但未命中的公告会追加抓取职位列表子页二次匹配。

**科学人才网**：PC 列表页有 WAF，但职位详情页 `/job/{id}.html` 完全开放且 ID
连续。前沿用「上探 + 二分」发现（约 15 个请求），抓取后从标题解析单位与岗位名。

**事业单位招聘网（shiyebian.net）**：纯静态 GBK 站，文章 ID 递增。覆盖自然资源部
海洋一/二/三/四所、部属单位（海洋技术中心、海洋信息中心、极地中心、深海基地等）
的事业编公开招聘，地方海洋局/自然资源局公告也有收录。

**高校人才网职位页（m.gaoxiaojob.com）**：公告拆分后的具体职位，带需求专业、
工作地点、薪资字段，是化学岗位匹配的金标准（专业含化学+海洋语境即命中）。

**机构类规则**（config.yaml）：
- `ocean_org_words`：标题含海洋局/自然资源部/海区局/海洋中心等 → 直接收录
- `soe_rules`：央企国企（中海油/中船/中远海运等直接命中；中交/电建/能建等
  需叠加海洋语境词）

## 用法

```bash
pip install -r requirements.txt

python run_collect.py                          # 全来源增量采集
python run_collect.py --only sciencehr --backfill 1000
python run_collect.py --backfill 20000         # 全量历史回填（可分多次，断点续跑）
powershell -File run_backfill.ps1              # 后台完整回填（日志 collect.log）
python build_site.py                           # 重新生成 site/
```

## 部署

推送到 GitHub 后：
1. 仓库 Settings → Pages → Source 选 `gh-pages` 分支（workflows 会自动创建）
2. Actions 会在每天 08:30（北京时间）自动采集、构建并发布

## 合规说明

- 仅抓取公开页面，遵循 robots.txt，请求间隔 0.4–0.9s
- 每条信息注明来源与原文链接，以官方公告为准
- 请勿用于商业用途
