import os
import httpx

_API_KEY  = os.getenv("RESEND_API_KEY", "")
_FROM     = os.getenv("RESEND_FROM_EMAIL", "AOリサーチ <noreply@helphero.jp>")
_APP_URL  = os.getenv("APP_URL", "https://ao.helphero.jp")


async def send_welcome_email(name: str, email: str) -> None:
    if not _API_KEY:
        return

    first = name.split()[0] if name else "さん"
    html = f"""<!DOCTYPE html>
<html lang="ja">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head>
<body style="margin:0;padding:0;background:#f5f7fa;font-family:'Helvetica Neue',Arial,sans-serif;">
  <table width="100%" cellpadding="0" cellspacing="0" style="background:#f5f7fa;padding:32px 0;">
    <tr><td align="center">
      <table width="560" cellpadding="0" cellspacing="0" style="background:#ffffff;border-radius:12px;overflow:hidden;max-width:560px;width:100%;">

        <!-- ヘッダー -->
        <tr>
          <td style="background:#2563eb;padding:32px 40px;text-align:center;">
            <p style="margin:0;color:#93c5fd;font-size:13px;letter-spacing:0.05em;">総合型選抜リサーチツール</p>
            <h1 style="margin:8px 0 0;color:#ffffff;font-size:24px;font-weight:700;">AOリサーチ</h1>
          </td>
        </tr>

        <!-- 本文 -->
        <tr>
          <td style="padding:40px 40px 32px;">
            <p style="margin:0 0 8px;color:#1e293b;font-size:18px;font-weight:600;">{first}さん、登録ありがとうございます！</p>
            <p style="margin:0 0 28px;color:#64748b;font-size:15px;line-height:1.7;">
              AOリサーチは大学の公式HP・募集要項PDFをAIがリサーチして、志願者数・倍率・選考内容をまとめて表示するツールです。
            </p>

            <!-- 使い方 3ステップ -->
            <table width="100%" cellpadding="0" cellspacing="0" style="margin-bottom:32px;">
              <tr>
                <td style="background:#eff6ff;border-radius:10px;padding:24px 28px;">
                  <p style="margin:0 0 16px;color:#1e40af;font-size:13px;font-weight:700;letter-spacing:0.05em;">▶ かんたん3ステップ</p>
                  <table width="100%" cellpadding="0" cellspacing="0">
                    <tr>
                      <td style="padding-bottom:12px;">
                        <span style="display:inline-block;background:#2563eb;color:#fff;border-radius:50%;width:22px;height:22px;text-align:center;line-height:22px;font-size:12px;font-weight:700;margin-right:10px;">1</span>
                        <span style="color:#1e293b;font-size:14px;">大学名・学部名を入力する</span>
                      </td>
                    </tr>
                    <tr>
                      <td style="padding-bottom:12px;">
                        <span style="display:inline-block;background:#2563eb;color:#fff;border-radius:50%;width:22px;height:22px;text-align:center;line-height:22px;font-size:12px;font-weight:700;margin-right:10px;">2</span>
                        <span style="color:#1e293b;font-size:14px;">AIが一次情報（公式HP・PDF）を自動収集</span>
                      </td>
                    </tr>
                    <tr>
                      <td>
                        <span style="display:inline-block;background:#2563eb;color:#fff;border-radius:50%;width:22px;height:22px;text-align:center;line-height:22px;font-size:12px;font-weight:700;margin-right:10px;">3</span>
                        <span style="color:#1e293b;font-size:14px;">志願者数・倍率・選考内容がまとまってレポート完成</span>
                      </td>
                    </tr>
                  </table>
                </td>
              </tr>
            </table>

            <!-- 無料回数の案内 -->
            <p style="margin:0 0 28px;color:#64748b;font-size:14px;line-height:1.7;">
              無料プランでは<strong style="color:#1e293b;">3回まで</strong>リサーチできます。まずは気になる大学を調べてみてください。
            </p>

            <!-- CTA -->
            <table width="100%" cellpadding="0" cellspacing="0">
              <tr>
                <td align="center">
                  <a href="{_APP_URL}" style="display:inline-block;background:#2563eb;color:#ffffff;text-decoration:none;font-size:16px;font-weight:700;padding:16px 48px;border-radius:8px;">
                    今すぐリサーチしてみる
                  </a>
                </td>
              </tr>
            </table>
          </td>
        </tr>

        <!-- フッター -->
        <tr>
          <td style="border-top:1px solid #e2e8f0;padding:24px 40px;text-align:center;">
            <p style="margin:0;color:#94a3b8;font-size:12px;line-height:1.6;">
              AOリサーチ │ <a href="{_APP_URL}" style="color:#94a3b8;">{_APP_URL}</a><br>
              このメールは登録時に自動送信されています。
            </p>
          </td>
        </tr>

      </table>
    </td></tr>
  </table>
</body>
</html>"""

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            await client.post(
                "https://api.resend.com/emails",
                headers={"Authorization": f"Bearer {_API_KEY}"},
                json={
                    "from": _FROM,
                    "to":   [email],
                    "subject": f"【AOリサーチ】登録ありがとうございます、{first}さん",
                    "html": html,
                },
            )
    except Exception:
        pass  # メール失敗で登録を壊さない
