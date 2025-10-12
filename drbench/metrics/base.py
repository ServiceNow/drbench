"""Base metric class with standardized interface."""

from abc import ABC, abstractmethod
from typing import Any, Dict


class DrBenchMetric(ABC):
    """
    Base class for all DrBench metrics with standardized output.
    """

    def __init__(self, name: str, **config):
        self.name = name
        self.config = config

    @abstractmethod
    def compute(
        self,
        report_dict: Dict[str, Any],
        task_data: Dict[str, Any],
        eval_data: Dict[str, Any],
        **kwargs,
    ) -> dict:
        """
        Compute the metric and return standardized result.

        Args:
            report_dict: Dictionary containing 'report_text' and 'report_insights'
            task_data: Task-specific data (question, etc.)
            eval_data: Evaluation data (ground truth, etc.)
            **kwargs: Additional arguments (e.g., pred_report_metadata)

        Returns:
            MetricResult: Standardized metric result with score, metadata, etc.
        """
        raise NotImplementedError("Subclasses must implement this method.")

    def format_summary(self, result) -> str:
        """
        Format a metric result for display in reports.

        Subclasses can override this to provide custom formatting that
        makes sense for their metric type.

        Args:
            result: The MetricResult to format

        Returns:
            str: Formatted summary for this metric
        """
        # Default implementation - subclasses should override
        lines = [f"Score: {result.score:.4f}"]

        if result.sample_scores:
            lines.append(f"Samples: {len(result.sample_scores)}")
            lines.append(
                f"  Mean: {sum(result.sample_scores)/len(result.sample_scores):.4f}"
            )
            lines.append(
                f"  Range: {min(result.sample_scores):.4f} - {max(result.sample_scores):.4f}"
            )

        # Show key metadata values if available
        if result.metadata:
            for key, value in result.metadata.items():
                if key in ["model", "num_samples", "n_samples"]:
                    lines.append(f"{key}: {value}")

        return "\n".join(lines)

    def format_short_summary(self, result) -> str:
        """
        Format a brief one-line summary for metric scores.

        Used in the main scores section of reports.
        """
        return f"{result.score:.4f}"

    def __str__(self):
        return f"{self.__class__.__name__}(name={self.name})"

    def __repr__(self):
        return f"{self.__class__.__name__}(name='{self.name}', config={self.config})"
