"""
Tests for backward-compatible changes to drbench metrics and score_report.

These tests guard against regressions in:
  - metrics/__init__.py  : get_metric() accepts embedding_model kwarg
  - metrics/factuality_v2.py : CitationFactuality accepts embedding_model=None default
  - score_report.py      : score_report() accepts embedding_model kwarg
"""

import inspect
import pytest
from unittest.mock import patch, MagicMock

from drbench.metrics import get_metric
from drbench.metrics.factuality_v2 import CitationFactuality


# ---------------------------------------------------------------------------
# CitationFactuality
# ---------------------------------------------------------------------------

class TestCitationFactuality:
    def test_default_construction_unchanged(self):
        """Old callers passing only model= must still work."""
        m = CitationFactuality(model="gpt-4o-mini")
        assert m.model == "gpt-4o-mini"
        assert m.name == "factuality"

    def test_embedding_model_default_is_none(self):
        """Default embedding_model must be None so utils fallback logic is used."""
        m = CitationFactuality(model="gpt-4o-mini")
        assert m.embedding_model is None

    def test_embedding_model_explicit(self):
        """Explicit embedding_model is stored correctly."""
        m = CitationFactuality(model="gpt-4o-mini", embedding_model="openai/text-embedding-3-small")
        assert m.embedding_model == "openai/text-embedding-3-small"

    def test_metric_name_is_factuality(self):
        """name must stay 'factuality' to match drbench_public output keys."""
        m = CitationFactuality(model="gpt-4o-mini")
        assert m.name == "factuality"


# ---------------------------------------------------------------------------
# get_metric
# ---------------------------------------------------------------------------

class TestGetMetric:
    def test_factuality_name_returns_citation_factuality(self):
        m = get_metric("factuality", model="gpt-4o-mini")
        assert isinstance(m, CitationFactuality)

    def test_get_metric_embedding_model_param_accepted(self):
        """get_metric must accept embedding_model without raising."""
        m = get_metric("factuality", model="gpt-4o-mini", embedding_model="openai/text-embedding-3-small")
        assert m.embedding_model == "openai/text-embedding-3-small"

    def test_get_metric_embedding_model_default_none(self):
        m = get_metric("factuality", model="gpt-4o-mini")
        assert m.embedding_model is None

    def test_other_metrics_unaffected(self):
        from drbench.metrics.qa_similarity_v2 import QASimilarityV2
        from drbench.metrics.distractor_recall import DistractorRecall
        from drbench.metrics.report_quality import ReportQuality

        assert isinstance(get_metric("insights_recall", model="gpt-4o-mini"), QASimilarityV2)
        assert isinstance(get_metric("distractor_recall", model="gpt-4o-mini"), DistractorRecall)
        assert isinstance(get_metric("report_quality", model="gpt-4o-mini"), ReportQuality)

    def test_unknown_metric_raises(self):
        with pytest.raises(ValueError, match="Unknown metric"):
            get_metric("nonexistent_metric")


# ---------------------------------------------------------------------------
# score_report signature
# ---------------------------------------------------------------------------

class TestScoreReportSignature:
    def test_embedding_model_param_exists(self):
        """score_report must accept embedding_model kwarg (backward-compatible add)."""
        from drbench.score_report import score_report
        sig = inspect.signature(score_report)
        assert "embedding_model" in sig.parameters

    def test_embedding_model_default_is_none(self):
        from drbench.score_report import score_report
        sig = inspect.signature(score_report)
        assert sig.parameters["embedding_model"].default is None
