"""
/api/research エンドポイント群 + /api/me
"""
import asyncio
from datetime import datetime, timezone

from fastapi import APIRouter, BackgroundTasks, HTTPException, Request
from pydantic import BaseModel, Field

from core.university import create_job, get_job, run_research_job, save_to_notion_sync
from auth.deps import get_current_user, get_client_ip, FREE_LIMIT

router = APIRouter(prefix="/api", tags=["research"])


# ── スキーマ ──────────────────────────────────────────────────────────────────

class ResearchRequest(BaseModel):
    university: str = Field(..., min_length=1, max_length=100, description="大学名")
    faculty:    str = Field(default="", max_length=100, description="学部名（省略可）")
    department: str = Field(default="", max_length=100, description="学科名（省略可）")
    pdf_url:    str = Field(default="", max_length=500, description="募集要項PDFのURL（省略可）")


class SimilarSchoolsRequest(BaseModel):
    job_id: str = Field(..., description="完了済みリサーチのジョブID")


class CompareRequest(BaseModel):
    job_ids: list[str] = Field(..., min_length=2, max_length=4, description="比較するジョブIDのリスト（2〜4件）")


class CompareNotionRequest(BaseModel):
    job_ids: list[str] = Field(..., min_length=2, max_length=4)


class JobCreatedResponse(BaseModel):
    job_id:  str
    message: str


class JobStatusResponse(BaseModel):
    job_id:     str
    status:     str
    progress:   list[str]
    result:     dict | None
    error:      str | None
    created_at: str


# ── 利用制限ヘルパー ─────────────────────────────────────────────────────────

def _check_and_increment(user: dict | None, request: Request) -> None:
    """フリープラン（ログイン済み / 未ログイン）の月3回制限を確認してインクリメント。"""
    from database import get_db
    now    = datetime.now(timezone.utc)
    now_s  = now.isoformat()
    cur_ym = (now.year, now.month)

    if user:
        if user["plan"] == "standard":
            return  # 無制限

        db = get_db()
        try:
            row    = db.execute(
                "SELECT usage_count, usage_reset_at FROM users WHERE id = ?",
                (user["user_id"],),
            ).fetchone()
            count  = row["usage_count"]
            reset  = row["usage_reset_at"]

            # 月が変わっていたらリセット
            if reset:
                rd = datetime.fromisoformat(reset)
                if (rd.year, rd.month) != cur_ym:
                    count = 0
                    db.execute(
                        "UPDATE users SET usage_count=0, usage_reset_at=? WHERE id=?",
                        (now_s, user["user_id"]),
                    )
                    db.commit()
            else:
                db.execute("UPDATE users SET usage_reset_at=? WHERE id=?", (now_s, user["user_id"]))
                db.commit()

            if count >= FREE_LIMIT:
                raise HTTPException(
                    status_code=429,
                    detail=f"月間利用上限（{FREE_LIMIT}回）に達しました。スタンダードプランへのアップグレードをご検討ください。",
                )

            db.execute("UPDATE users SET usage_count = usage_count + 1 WHERE id = ?", (user["user_id"],))
            db.commit()
        finally:
            db.close()

    else:
        # 未ログイン：IP ベースで月3回まで
        ip = get_client_ip(request)
        db = get_db()
        try:
            row = db.execute("SELECT usage_count, reset_at FROM anon_usage WHERE ip = ?", (ip,)).fetchone()
            if row:
                count = row["usage_count"]
                reset = row["reset_at"]
                if reset:
                    rd = datetime.fromisoformat(reset)
                    if (rd.year, rd.month) != cur_ym:
                        count = 0
                        db.execute(
                            "UPDATE anon_usage SET usage_count=0, reset_at=? WHERE ip=?",
                            (now_s, ip),
                        )
                        db.commit()

                if count >= FREE_LIMIT:
                    raise HTTPException(
                        status_code=429,
                        detail=f"未ログインの場合、月{FREE_LIMIT}回まで無料でご利用いただけます。ログインするとさらにご利用いただけます。",
                    )

                db.execute("UPDATE anon_usage SET usage_count = usage_count + 1 WHERE ip = ?", (ip,))
            else:
                db.execute("INSERT INTO anon_usage (ip, usage_count, reset_at) VALUES (?, 1, ?)", (ip, now_s))

            db.commit()
        finally:
            db.close()


# ── エンドポイント ────────────────────────────────────────────────────────────

@router.post("/research", response_model=JobCreatedResponse, summary="調査ジョブを開始")
async def start_research(req: ResearchRequest, background_tasks: BackgroundTasks, request: Request):
    user = get_current_user(request)
    _check_and_increment(user, request)

    job_id = create_job()
    background_tasks.add_task(
        run_research_job, job_id, req.university, req.faculty, req.department, req.pdf_url
    )
    return JobCreatedResponse(job_id=job_id, message="調査を開始しました")


@router.get("/research/{job_id}", response_model=JobStatusResponse, summary="ジョブ状態・結果を取得")
async def get_research_status(job_id: str):
    job = get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="ジョブが見つかりません")
    return JobStatusResponse(job_id=job_id, **job)


@router.post("/research/{job_id}/notion", summary="結果を Notion に保存")
async def save_notion(job_id: str, request: Request):
    job = get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="ジョブが見つかりません")
    if job["status"] != "done":
        raise HTTPException(status_code=409, detail=f"ジョブが完了していません（status: {job['status']}）")
    try:
        result = await asyncio.to_thread(save_to_notion_sync, job_id)
        return result
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/me", summary="現在のログインユーザー情報を取得")
async def get_me(request: Request):
    user = get_current_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="認証が必要です")
    from database import get_db
    db = get_db()
    try:
        row = db.execute(
            "SELECT id, name, email, plan, usage_count, picture FROM users WHERE id = ?",
            (user["user_id"],),
        ).fetchone()
        if not row:
            raise HTTPException(status_code=401, detail="ユーザーが見つかりません")
        return dict(row)
    finally:
        db.close()


@router.post("/compare", summary="複数大学の比較表を生成")
async def compare_schools(body: CompareRequest):
    schools = []
    for job_id in body.job_ids:
        job = get_job(job_id)
        if not job or job["status"] != "done":
            raise HTTPException(status_code=400, detail=f"ジョブ {job_id} が完了していません")
        result  = job["result"] or {}
        ud      = result.get("university_data", {})
        univs   = ud.get("step_c", {}).get("universities", ud.get("universities", []))
        u0      = univs[0] if univs else {}
        step_a  = ud.get("step_a", {})
        rh      = u0.get("ratio_history", {})
        ratio   = " / ".join(rh.get(y, "?") for y in ["2026", "2025", "2024"])
        schools.append({
            "job_id":           job_id,
            "university":       result.get("university", u0.get("university", "")),
            "faculty":          result.get("faculty",    u0.get("faculty", "")),
            "department":       result.get("department", u0.get("department", "")),
            "application_period": u0.get("application_period", ""),
            "selection_methods":  u0.get("selection_methods", []),
            "selection_detail":   u0.get("selection_detail", ""),
            "quota":            u0.get("quota", ""),
            "ratio":            ratio,
            "eligibility":      u0.get("eligibility") or u0.get("application_requirements", ""),
            "gpa_requirement":  u0.get("gpa_requirement", ""),
            "ap":               step_a.get("ap_university") or step_a.get("admission_policy", ""),
        })
    return {"schools": schools}


@router.post("/compare/notion", summary="比較結果をNotionに保存")
async def compare_to_notion(body: CompareNotionRequest):
    import os, httpx
    token = os.environ.get("NOTION_TOKEN", "")
    if not token:
        raise HTTPException(status_code=503, detail="NOTION_TOKEN が設定されていません")

    # 比較データ収集
    schools = []
    for job_id in body.job_ids:
        job = get_job(job_id)
        if not job or job["status"] != "done":
            continue
        result = job["result"] or {}
        ud     = result.get("university_data", {})
        univs  = ud.get("step_c", {}).get("universities", ud.get("universities", []))
        u0     = univs[0] if univs else {}
        step_a = ud.get("step_a", {})
        rh     = u0.get("ratio_history", {})
        schools.append({
            "university":  result.get("university", u0.get("university", "")),
            "faculty":     result.get("faculty", u0.get("faculty", "")),
            "selection":   " / ".join(u0.get("selection_methods", [u0.get("selection_detail", "")])),
            "period":      u0.get("application_period", ""),
            "quota":       u0.get("quota", ""),
            "ratio":       " / ".join(rh.get(y, "?") for y in ["2026", "2025", "2024"]),
            "eligibility": u0.get("eligibility") or u0.get("application_requirements", ""),
            "gpa":         u0.get("gpa_requirement", ""),
            "ap":          (step_a.get("ap_university") or "")[:200],
        })

    if not schools:
        raise HTTPException(status_code=400, detail="比較できるジョブがありません")

    # Notion ページ本文を組み立て
    PARENT_ID = "3302c0f3-8d2d-81aa-b102-cca314b0ee0a"
    title = "比較: " + " vs ".join(f"{s['university']} {s['faculty']}" for s in schools)
    ROWS = [
        ("出願期間",  "period"),
        ("選考方法",  "selection"),
        ("定員",     "quota"),
        ("倍率(26/25/24)", "ratio"),
        ("出願条件",  "eligibility"),
        ("評定条件",  "gpa"),
        ("AP要旨",   "ap"),
    ]

    def txt(s):
        return {"type": "text", "text": {"content": s[:500] if s else "—"}}

    children = []
    # 見出し行（リッチテキスト疑似ヘッダー）
    header_text = "比較項目 | " + " | ".join(f"{s['university']} {s['faculty']}" for s in schools)
    children.append({"object": "block", "type": "heading_2",
                      "heading_2": {"rich_text": [txt(header_text)]}})
    # 各行
    for label, key in ROWS:
        row_text = f"{label}: " + " | ".join(s.get(key, "") or "—" for s in schools)
        children.append({"object": "block", "type": "paragraph",
                          "paragraph": {"rich_text": [txt(row_text)]}})

    payload = {
        "parent": {"type": "page_id", "page_id": PARENT_ID},
        "properties": {"title": {"title": [txt(title)]}},
        "children": children,
    }
    async with httpx.AsyncClient() as c:
        r = await c.post(
            "https://api.notion.com/v1/pages",
            headers={"Authorization": f"Bearer {token}", "Notion-Version": "2022-06-28"},
            json=payload, timeout=15,
        )
        if not r.is_success:
            raise HTTPException(status_code=502, detail=f"Notion API エラー: {r.text[:120]}")
    return {"saved": True, "title": title}


@router.post("/similar-schools", summary="類似校を提案")
async def similar_schools(body: SimilarSchoolsRequest):
    from core.similar_schools import suggest_similar_schools

    job = get_job(body.job_id)
    if not job:
        raise HTTPException(status_code=404, detail="ジョブが見つかりません")
    if job["status"] != "done":
        raise HTTPException(status_code=400, detail="リサーチ完了後に類似校を取得してください")

    result = job["result"] or {}
    try:
        schools = await asyncio.to_thread(
            suggest_similar_schools,
            result.get("university", ""),
            result.get("faculty", ""),
            result.get("department", ""),
            result.get("university_data", {}),
        )
        return {"schools": schools}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/health", summary="ヘルスチェック")
async def health():
    return {"status": "ok"}
