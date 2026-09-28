# 每日增量（GitHub Actions 用 run_collect.py 无参数即可全来源增量）
# 本脚本用于本地全量历史回填（断点续跑）
python run_collect.py --only gaoxiaojob --backfill 20000 --log collect.log
python run_collect.py --only sciencehr --backfill 3000 --log collect.log
python run_collect.py --only shiyebian --backfill 8000 --log collect.log
python run_collect.py --only gaoxiaojob_job --backfill 15000 --log collect.log
python build_site.py
Add-Content -Path collect.log -Value "backfill all done"
