"""Branded HTML email body for collections outreach.

Wraps the Gemini-composed (tone-adapted, bilingual) message in a Bank Muamalat
shell: brand header, DPD-stage status strip, a payment-summary card and a CTA.
Returns (subject, html); the plain-text message is sent as the fallback part.
Table-based layout + inline styles for broad email-client support.
"""
import html as _html

# stage -> (accent colour, Malay status label, subject label)
_STAGE = {
    "SOFT_REMINDER":  ("#2E7D32", "Peringatan Mesra",  "Peringatan Mesra"),
    "INTENSIVE":      ("#F9A825", "Notis Pembayaran",  "Notis Pembayaran"),
    "FIELD_VISIT":    ("#EF6C00", "Notis Penting",     "Notis Penting"),
    "RECOVERY_LEGAL": ("#C62828", "Notis Rasmi",       "Notis Rasmi"),
}
_BRAND = "#00504A"       # Bank Muamalat deep teal
_BRAND_LIGHT = "#00695C"


def render(name: str, message_text: str, facts) -> tuple[str, str]:
    accent, label, subj_label = _STAGE.get(facts.stage, _STAGE["SOFT_REMINDER"])
    amount = f"RM {facts.outstanding:,.2f}"
    loan = _html.escape(facts.loan_id or "-")
    safe_name = _html.escape(name or "Pelanggan")
    body_html = _html.escape(message_text or "").replace("\n", "<br>")
    subject = f"{subj_label} — Bank Muamalat" + (f" (Akaun {loan})" if facts.loan_id else "")

    html = f"""\
<!DOCTYPE html>
<html lang="ms"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{subject}</title></head>
<body style="margin:0;padding:0;background:#f4f5f7;font-family:-apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif;color:#1a1a1a;">
<span style="display:none;max-height:0;overflow:hidden;opacity:0;">Tunggakan {amount} bagi akaun {loan} — {label} daripada Bank Muamalat.</span>
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#f4f5f7;padding:24px 12px;">
<tr><td align="center">
  <table role="presentation" width="600" cellpadding="0" cellspacing="0" style="max-width:600px;width:100%;background:#ffffff;border-radius:12px;overflow:hidden;box-shadow:0 1px 4px rgba(0,0,0,0.08);">
    <!-- brand header -->
    <tr><td style="background:{_BRAND};padding:20px 28px;">
      <table role="presentation" width="100%"><tr>
        <td style="color:#ffffff;font-size:19px;font-weight:700;letter-spacing:0.3px;">Bank&nbsp;Muamalat</td>
        <td align="right" style="color:#bfe3da;font-size:11px;text-transform:uppercase;letter-spacing:1px;">Islamic Banking</td>
      </tr></table>
    </td></tr>
    <!-- status strip -->
    <tr><td style="background:{accent};height:6px;line-height:6px;font-size:0;">&nbsp;</td></tr>
    <tr><td style="padding:22px 28px 6px;">
      <span style="display:inline-block;background:{accent}1a;color:{accent};font-size:12px;font-weight:700;padding:5px 12px;border-radius:999px;text-transform:uppercase;letter-spacing:0.5px;">{label}</span>
    </td></tr>
    <!-- personalised message -->
    <tr><td style="padding:14px 28px 4px;font-size:15px;line-height:1.6;color:#2a2a2a;">{body_html}</td></tr>
    <!-- payment summary card -->
    <tr><td style="padding:18px 28px 6px;">
      <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#f7f9f9;border:1px solid #e3e8e8;border-radius:10px;">
        <tr>
          <td style="padding:14px 18px;font-size:13px;color:#5a6a6a;">Akaun Pembiayaan</td>
          <td align="right" style="padding:14px 18px;font-size:13px;font-weight:600;color:#1a1a1a;">{loan}</td>
        </tr>
        <tr><td colspan="2" style="border-top:1px solid #e3e8e8;font-size:0;line-height:0;">&nbsp;</td></tr>
        <tr>
          <td style="padding:14px 18px;font-size:13px;color:#5a6a6a;">Hari Tertunggak (DPD)</td>
          <td align="right" style="padding:14px 18px;font-size:13px;font-weight:600;color:#1a1a1a;">{facts.dpd} hari</td>
        </tr>
        <tr><td colspan="2" style="border-top:1px solid #e3e8e8;font-size:0;line-height:0;">&nbsp;</td></tr>
        <tr>
          <td style="padding:16px 18px;font-size:13px;color:#5a6a6a;">Jumlah Tertunggak</td>
          <td align="right" style="padding:16px 18px;font-size:22px;font-weight:800;color:{accent};">{amount}</td>
        </tr>
      </table>
    </td></tr>
    <!-- CTA -->
    <tr><td align="center" style="padding:20px 28px 8px;">
      <a href="https://www.muamalat.com.my" style="display:inline-block;background:{_BRAND_LIGHT};color:#ffffff;text-decoration:none;font-size:15px;font-weight:700;padding:13px 34px;border-radius:8px;">Buat Pembayaran</a>
    </td></tr>
    <tr><td align="center" style="padding:0 28px 20px;font-size:13px;color:#5a6a6a;">Perlukan bantuan? Hubungi kami di <a href="tel:1300888787" style="color:{_BRAND_LIGHT};text-decoration:none;font-weight:600;">1300-88-8787</a></td></tr>
    <!-- footer -->
    <tr><td style="background:#f7f9f9;border-top:1px solid #e3e8e8;padding:18px 28px;font-size:11px;line-height:1.6;color:#8a9a9a;">
      Pembiayaan patuh Syariah — tiada faedah (riba) atau caj penalti berganda dikenakan.<br>
      E-mel ini dijana secara automatik untuk tujuan peringatan pembayaran. Sila abaikan jika anda telah menjelaskan bayaran.<br>
      &copy; Bank Muamalat Malaysia Berhad.
    </td></tr>
  </table>
</td></tr>
</table>
</body></html>"""
    return subject, html
