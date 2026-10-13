"""ML classifier integration tests (rules+ml fusion signal)."""
from app.services.ml_classifier import get_ml_classifier, classify_with_ml
from app.services.input_manager import analyze_input


class TestMLClassifier:
    def test_classifier_loads_or_neutral(self):
        clf = get_ml_classifier()
        res = clf.predict("Your account will be blocked today. Send the OTP now.")
        assert 0 <= res.score <= 100
        assert 0.0 <= res.probability <= 1.0
        assert res.label in ("scam", "legitimate", "uncertain")

    def test_pipeline_includes_ml_evidence_when_available(self):
        clf = get_ml_classifier()
        result = analyze_input(text="Pay Rs 999 registration fee today to confirm internship seat.")
        sources = {e["source"] for e in result.evidence}
        if clf.is_available():
            assert "ml" in sources
            assert result.mode == "rules+ml"
            assert "ml" in result.module_scores
        else:
            assert result.mode in ("rules", "rules+ml")

    def test_score_invariant_holds_with_ml(self):
        result = analyze_input(text="Congratulations! Selected for job. Pay Rs 2000 fee, no interview.")
        total = sum(e["weight"] for e in result.evidence)
        assert result.risk_score == min(100, max(0, total))
