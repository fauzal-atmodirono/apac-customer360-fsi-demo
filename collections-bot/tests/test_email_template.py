from conversation import CaseFacts
from email_template import render


def test_render_includes_brand_amount_loan_and_message():
    facts = CaseFacts(stage="RECOVERY_LEGAL", dpd=120, outstanding=8323.0, loan_id="LN9", name="Encik Tan")
    subject, html = render("Encik Tan", "Salam Encik Tan, sila jelaskan bayaran.", facts)
    assert "Bank Muamalat" in html
    assert "RM 8,323.00" in html          # formatted amount
    assert "LN9" in html                   # loan id + subject
    assert "LN9" in subject
    assert "120 hari" in html              # DPD
    assert "sila jelaskan bayaran" in html # the composed message is embedded


def test_render_escapes_message_and_keeps_line_breaks():
    facts = CaseFacts(stage="SOFT_REMINDER", dpd=10, outstanding=100.0, loan_id="LN1", name="Ali")
    _, html = render("Ali", "line1\n<script>bad</script>", facts)
    assert "&lt;script&gt;" in html        # escaped, not raw
    assert "<script>bad" not in html
    assert "line1<br>" in html             # newline -> <br>


def test_render_accent_differs_by_stage():
    soft = render("A", "x", CaseFacts("SOFT_REMINDER", 10, 1.0, "L", "A"))[1]
    legal = render("A", "x", CaseFacts("RECOVERY_LEGAL", 120, 1.0, "L", "A"))[1]
    assert "#2E7D32" in soft   # green for soft reminder
    assert "#C62828" in legal  # red for legal
