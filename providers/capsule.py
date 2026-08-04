"""时间胶囊：从本机 git 仓库历史里找"同一天，一年前/一个月前的自己"。

数据源全部本地、零外部依赖：扫描 config.json 里 `capsule_repos` 列出的
仓库（默认是这个项目自己 + pocket-prophet-dashboard，用户可以在设置里加
更多），对每个候选日期窗口跑 `git log --since/--until`，凑出一条 commit
message。找不到就老实说找不到，不编造。
"""
from __future__ import annotations

import subprocess
from datetime import datetime, timedelta

import config

# 候选回溯窗口，按"更有纪念意义"优先：一年前 > 一个月前 > 一周前
CANDIDATE_OFFSETS = [
    ("一年前", timedelta(days=365)),
    ("一个月前", timedelta(days=30)),
    ("一周前", timedelta(days=7)),
]


def _commits_on_day(repo: str, day: datetime) -> list[str]:
    since = day.strftime("%Y-%m-%d 00:00:00")
    until = (day + timedelta(days=1)).strftime("%Y-%m-%d 00:00:00")
    try:
        out = subprocess.run(
            ["git", "-C", repo, "log", f"--since={since}", f"--until={until}", "--pretty=%s"],
            capture_output=True, text=True, timeout=5,
        ).stdout
    except (subprocess.SubprocessError, OSError):
        return []
    return [line for line in out.splitlines() if line.strip()]


def fetch(repos: list[str] = None) -> dict:
    """返回 {"label": "一年前", "date": "...", "message": "...", "repo": "..."}
    或 {"label": None, "message": "今天没有留下记录"}（找不到任何候选时）。
    """
    repos = repos or config.path_list_setting("capsule_repos")
    now = datetime.now()

    for label, offset in CANDIDATE_OFFSETS:
        day = now - offset
        for repo in repos:
            commits = _commits_on_day(repo, day)
            if commits:
                import secrets
                msg = secrets.choice(commits)
                return {
                    "label": label,
                    "date": day.strftime("%Y-%m-%d"),
                    "message": msg,
                    "repo": repo.rsplit("/", 1)[-1],
                }

    return {"label": None, "date": None, "message": "今天没有留下记录", "repo": None}
