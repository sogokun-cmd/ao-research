"""
類似校提案モジュール
university_data をもとに入試方式・評定条件・難易度・地域が近い大学を提案する
"""
import json
import os

from anthropic import Anthropic

_client: Anthropic | None = None


def _get_client() -> Anthropic:
    global _client
    if _client is None:
        _client = Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY", ""))
    return _client


def suggest_similar_schools(
    university: str,
    faculty: str,
    department: str,
    university_data: dict,
) -> list[dict]:
    """
    university_data をもとに類似校を 3〜5 校提案する。

    Returns list of:
    {
      name: str,                    # 大学名
      faculty: str,                 # 学部名
      department: str,              # 学科名（任意）
      admission_type: str,          # 入試方式（例: 書類＋面接型）
      difficulty: str,              # 難易度帯
      region: str,                  # 地域
      similarity_points: list[str], # 類似理由（例: 同じ小論文型）
      note: str,                    # 一言コメント
    }
    """
    # university_data を要約して prompt に渡す（長すぎると token 超過）
    data_summary = _summarize_university_data(university_data)

    prompt = f"""あなたは総合型選抜（AO入試）の専門家です。
以下の大学・学部の総合型選抜情報を分析し、類似した総合型選抜を実施している日本の大学を3〜5校提案してください。

【調査対象】
大学: {university}
学部: {faculty}
学科: {department}

【取得済みの入試情報の要約】
{data_summary}

【提案基準（優先度順）】
1. 入試方式が近い（書類+面接、書類+小論文、書類+プレゼンなど）
2. 評定条件が近い（評定平均の要件）
3. 難易度・偏差値帯が近い
4. 地域（首都圏・関西・東海・地方など）
5. 総合型選抜の実施形態が似ている（2段階選考・1段階など）

以下の JSON のみを出力してください（説明文・コードブロック不要）：
{{"schools":[{{"name":"〇〇大学","faculty":"〇〇学部","department":"〇〇学科","admission_type":"書類＋面接型","difficulty":"中堅（偏差値50〜55程度）","region":"首都圏","similarity_points":["同じ小論文型","評定3.8以上の条件が近い","2段階選考"],"note":"論述力重視で出願条件も類似"}}]}}

必ず実在する日本の大学を提案し、JSON のみ出力してください。"""

    client = _get_client()
    resp = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=2048,
        messages=[{"role": "user", "content": prompt}],
    )

    text = resp.content[0].text.strip()
    start = text.find("{")
    end   = text.rfind("}") + 1
    if start == -1 or end == 0:
        return []

    data = json.loads(text[start:end])
    return data.get("schools", [])


def _summarize_university_data(data: dict) -> str:
    """university_data から提案に必要な情報だけ抽出してテキスト化する。"""
    lines: list[str] = []

    # step_c にある universities リスト
    universities = data.get("step_c", {}).get("universities", data.get("universities", []))
    for u in universities[:3]:  # 最大3件
        lines.append(f"・{u.get('university','')} {u.get('faculty','')} {u.get('department','')}")
        if u.get("selection_methods"):
            lines.append(f"  選考方法: {', '.join(u['selection_methods'])}")
        if u.get("application_requirements"):
            lines.append(f"  出願条件: {u['application_requirements'][:200]}")
        if u.get("quota"):
            lines.append(f"  定員: {u['quota']}")

    # アドミッションポリシー
    ap = (
        data.get("step_b", {}).get("admission_policy")
        or data.get("admission_policy", "")
    )
    if ap:
        lines.append(f"\nアドミッションポリシー（抜粋）: {str(ap)[:300]}")

    # 全体傾向
    trend = (
        data.get("step_d", {}).get("overall_trends")
        or data.get("overall_trends", "")
    )
    if trend:
        lines.append(f"\n全体傾向: {str(trend)[:200]}")

    return "\n".join(lines) if lines else json.dumps(data, ensure_ascii=False)[:1500]
