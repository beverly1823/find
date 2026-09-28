# 断点续跑：gaoxiaojob 剩余回填 -> 职位级回填 -> 重建站点（同域名顺序执行，避免并发触发限流）
python run_collect.py --only gaoxiaojob --backfill 20000 --log collect.log
python run_collect.py --only gaoxiaojob_job --backfill 15000 --log gjjob.log
python build_site.py
Add-Content -Path collect.log -Value "resume backfill done"
