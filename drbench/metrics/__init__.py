from drbench.metrics.distractor_recall import DistractorRecall
from drbench.metrics.factuality_v2 import CitationFactuality
from drbench.metrics.qa_similarity_v2 import QASimilarityV2
from drbench.metrics.report_quality import ReportQuality


def get_metric(name: str, model: str = "gpt-4o"):
    """
    Get metric by name.

    Args:
        name: The name of the metric to retrieve
        **kwargs: Additional parameters for the metric constructor

    Returns:
        DrBenchMetric: An instance of the requested metric class
    """
    if name == "insights_recall":
        return QASimilarityV2(
            model=model,
            n=5,
            ignore_not_answerable=False,
        )

    elif name == "distractor_recall":
        return DistractorRecall(
            model=model,
        )

    elif name == "report_quality":
        return ReportQuality(
            model=model,
        )

    elif name == "factuality":
        return CitationFactuality(
            model=model,
        )

    else:
        raise ValueError(f"Unknown metric name: {name}")
