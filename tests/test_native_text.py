import hashlib
import io

from reportlab.pdfgen.canvas import Canvas

from finn import documents


def source_pdf():
    output = io.BytesIO()
    canvas = Canvas(output)
    canvas.drawString(60, 750, "The company supplies consulting services to clients.")
    canvas.showPage()
    canvas.drawString(60, 750, "Consolidated accounts. INR in crore. March 31, 2026.")
    canvas.drawString(60, 730, "Reported loss (40). Missing value -; disclosed value nil.")
    canvas.save()
    return output.getvalue()


def test_native_pass_preserves_pages_source_and_unvalidated_units():
    data = source_pdf()
    result = documents.extract_document(
        data, {"source_url": "https://issuer.example/ar.pdf"}, native_text=True
    )
    assert result["sha256"] == hashlib.sha256(data).hexdigest()
    assert [p["pdf_page"] for p in result["pages"]] == [1, 2]
    assert "consulting services" in result["pages"][0]["reading_text"]
    assert "(40)" in result["pages"][1]["reading_text"]
    assert "March 31, 2026" in result["pages"][1]["metadata_candidates"]["period_labels"]
    assert result["pages"][1]["metadata_candidates"]["validated_for_financial_comparison"] is False
    assert result["financial_comparisons_enabled"] is False


def test_native_decode_failure_uses_same_source_pypdf_and_records_warning(monkeypatch):
    def broken(*args):
        raise UnicodeError("unreadable encoding")

    monkeypatch.setattr(documents, "native_page_texts", broken)
    data = source_pdf()
    result = documents.extract_document(
        data, {"source_url": "https://issuer.example/ar.pdf"}, native_text=True
    )
    assert result["sha256"] == hashlib.sha256(data).hexdigest()
    assert result["text_extractor"] == "pypdf"
    assert "consulting services" in result["pages"][0]["reading_text"]
    assert result["table_extraction_warnings"][0]["fallback"] == "pypdf_same_original_pdf"
