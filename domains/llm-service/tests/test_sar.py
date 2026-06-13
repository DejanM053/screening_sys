from app.ollama_client import OllamaClient
from app.sar import SarDraftGenerator
from tests.test_explain import SAMPLE_TREE

PAYMENT = {
    "originator_name": "Al-Qadir Trading LLC",
    "originator_country": "AE",
    "beneficiary_name": "Acme Holdings Ltd",
    "beneficiary_country": "GB",
    "amount_usd": 50000.0,
}


async def test_generate_falls_back_when_ollama_unreachable():
    ollama = OllamaClient(base_url="http://localhost:1", model="qwen2.5:14b", timeout_seconds=0.5)
    generator = SarDraftGenerator(ollama)

    draft = await generator.generate(
        payment_id="pay-1",
        verdict="REVIEW",
        composite_score=0.64,
        tree=SAMPLE_TREE,
        payment=PAYMENT,
        analyst_notes="Escalated for senior review",
    )

    assert "SUBJECT INFORMATION" in draft
    assert "Al-Qadir Trading LLC" in draft
    assert "Escalated for senior review" in draft
    assert "PARTIAL" in draft
