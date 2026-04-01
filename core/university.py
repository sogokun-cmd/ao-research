"""
ao_research.py の university / news / competitor モードを呼び出すラッパー。
重い処理（Web スクレイピング + Claude API）をバックグラウンドで実行し、
ジョブ単位で進捗・結果を管理する。
"""

import sys
import os
import uuid
import asyncio
from datetime import datetime
from pathlib import Path
from typing import Literal

# ao_research.py のあるディレクトリを sys.path に追加
_AO_RESEARCH_DIR = Path("/home/ryuu7")
if str(_AO_RESEARCH_DIR) not in sys.path:
    sys.path.insert(0, str(_AO_RESEARCH_DIR))

# ジョブストア（インメモリ）
# job_id → {"status", "progress", "result", "error", "created_at"}
_jobs: dict[str, dict] = {}

JobStatus = Literal["pending", "running", "done", "error"]


def create_job() -> str:
    job_id = str(uuid.uuid4())
    _jobs[job_id] = {
        "status": "pending",
        "progress": [],
        "result": None,
        "error": None,
        "created_at": datetime.now().isoformat(),
    }
    return job_id


def get_job(job_id: str) -> dict | None:
    return _jobs.get(job_id)


def _log(job_id: str, message: str):
    if job_id in _jobs:
        _jobs[job_id]["progress"].append(message)


async def run_research_job(job_id: str, university: str, faculty: str, department: str = "", pdf_url: str = ""):
    """バックグラウンドタスクとして実行。終了したらジョブストアに結果を格納。"""
    _jobs[job_id]["status"] = "running"
    parts = [p for p in [university, faculty, department] if p]
    keyword = " ".join(parts)
    if "総合型選抜" not in keyword:
        keyword = f"{keyword} 総合型選抜"

    try:
        result = await asyncio.to_thread(_run_sync, job_id, university, faculty, department, keyword, pdf_url)
        _jobs[job_id]["result"] = result
        _jobs[job_id]["status"] = "done"
    except Exception as exc:
        _jobs[job_id]["error"] = str(exc)
        _jobs[job_id]["status"] = "error"


def _run_sync(job_id: str, university: str, faculty: str, department: str, keyword: str, pdf_url: str = "") -> dict:
    """同期処理本体（別スレッドで実行される）。"""
    from dotenv import load_dotenv
    load_dotenv(dotenv_path=Path.home() / ".env")
    load_dotenv()

    import anthropic as _anthropic
    import ao_research as ao

    client = _anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

    # ── 1. 大学情報（university モード）
    _log(job_id, "Step0: PDF募集要項を検索・取得中...")
    _log(job_id, f"Step1-10: パスナビ・東進・公式サイト・倍率データを収集中... ({keyword})")
    university_data = ao.run_university_analysis(client, keyword, pdf_url=pdf_url)

    faculties_count = len(university_data.get("step_b", {}).get("faculties", []))
    unis_count = len(university_data.get("universities", []))
    _log(job_id, f"✓ 大学情報取得完了（{faculties_count}学部 / {unis_count}学科）")

    # ── 2. ニュース分析（news モード）
    _log(job_id, "ニュース・前年比変更点を分析中...")
    news_data = ao.run_news_analysis(client, keyword)
    _log(job_id, "✓ ニュース分析完了")

    # ── 3. 競合分析（competitor モード）
    _log(job_id, "競合大学のSNS戦略を分析中...")
    competitor_data = ao.run_competitor_analysis(client, keyword)
    accounts_count = len(competitor_data.get("top_accounts", []))
    _log(job_id, f"✓ 競合分析完了（{accounts_count}アカウント）")

    _log(job_id, "✅ 全分析完了")
    return {
        "university": university,
        "faculty": faculty,
        "department": department,
        "keyword": keyword,
        "university_data": university_data,
        "news_data": news_data,
        "competitor_data": competitor_data,
    }


def save_to_notion_sync(job_id: str) -> dict:
    """ジョブ結果を Notion に保存する（同期）。"""
    job = get_job(job_id)
    if job is None or job["status"] != "done" or not job["result"]:
        raise ValueError("ジョブが完了していないか結果がありません")

    from dotenv import load_dotenv
    load_dotenv(dotenv_path=Path.home() / ".env")
    load_dotenv()

    import ao_research as ao

    result = job["result"]
    keyword = result.get("keyword", "")
    full_results = {
        "university": result.get("university_data"),
        "news": result.get("news_data"),
        "competitor": result.get("competitor_data"),
    }

    ao.save_university_to_notion_hierarchical(full_results, keyword)
    ao.save_to_notion(full_results, keyword)
    return {"saved": True, "keyword": keyword}
