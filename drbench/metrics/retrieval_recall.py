"""Retrieval Recall metric with standardized output."""
from typing import Any, Dict, Set

from drbench.metrics.base import DrBenchMetric


class RetrievalRecall(DrBenchMetric):
    """
    Retrieval Recall metric for document retrieval evaluation.
    
    Measures what fraction of relevant documents were retrieved by the system.
    """

    def __init__(self, **kwargs):
        super().__init__(name="retrieval_recall", **kwargs)

    def compute(
        self, 
        report_dict: Dict[str, Any], 
        task_data: Dict[str, Any], 
        eval_data: Dict[str, Any], 
        **kwargs
    ) -> dict:
        """
        Compute retrieval recall score.

        Args:
            report_dict: Dictionary containing 'report_text' and 'report_insights'
            task_data: Task-specific data
            eval_data: Contains 'supporting_file_paths' with expected files
            **kwargs: May contain 'pred_report_metadata' with retrieved files

        Returns:
            dict: Standardized result with recall score and breakdown
        """
        # Extract expected and retrieved file paths
        expected_file_paths = eval_data.get("supporting_file_paths", [])
        report_metadata = kwargs.get("pred_report_metadata", {})
        retrieved_file_paths = report_metadata.get("document_ids", [])
        
        if not expected_file_paths:
            return {
                "score": 0.0,
                "summary": "No expected file paths provided",
                "metric_result": {
                    "num_expected": 0,
                    "num_retrieved": len(retrieved_file_paths),
                    "error": "No expected file paths provided"
                }
            }
        
        # Convert to sets for easier comparison
        expected_set = set(expected_file_paths)
        retrieved_set = set(retrieved_file_paths)
        
        # Calculate metrics
        true_positives = expected_set & retrieved_set
        recall = len(true_positives) / len(expected_set)
        
        # Additional metrics for detailed analysis
        precision = len(true_positives) / len(retrieved_set) if retrieved_set else 0.0
        f1_score = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0.0
        
        # Create summary
        summary = f"Recall: {recall:.4f}\n"
        summary += f"Retrieved {len(true_positives)}/{len(expected_set)} relevant documents\n"
        summary += f"Total documents retrieved: {len(retrieved_set)}"
        
        return {
            "score": recall,
            "summary": summary,
            "metric_result": {
                "num_expected": len(expected_set),
                "num_retrieved": len(retrieved_set),
                "num_relevant_retrieved": len(true_positives),
                "precision": precision,
                "f1_score": f1_score,
                "expected_files": list(expected_set),
                "retrieved_files": list(retrieved_set),
                "correctly_retrieved": list(true_positives),
                "missed_files": list(expected_set - retrieved_set),
                "extra_files": list(retrieved_set - expected_set)
            }
        }

    def format_summary(self, result: dict) -> str:
        """Format Retrieval Recall results for display."""
        recall = result["score"]
        metric_result = result.get("metric_result", {})
        
        num_expected = metric_result.get("num_expected", 0)
        num_retrieved = metric_result.get("num_retrieved", 0)
        num_relevant = metric_result.get("num_relevant_retrieved", 0)
        
        lines = [
            f"Recall: {recall:.4f}",
            f"Retrieved {num_relevant}/{num_expected} relevant documents",
            f"Total documents retrieved: {num_retrieved}",
        ]
        
        # Add breakdown if we have detailed info
        missed_files = metric_result.get("missed_files", [])
        if missed_files:
            lines.append(f"Missed {len(missed_files)} relevant documents")
                
        return "\n".join(lines)

    def format_short_summary(self, result: dict) -> str:
        """Format short summary for scores section."""
        metric_result = result.get("metric_result", {})
        num_relevant = metric_result.get("num_relevant_retrieved", 0)
        num_expected = metric_result.get("num_expected", 0)
        return f"{result['score']:.4f} ({num_relevant}/{num_expected} relevant)"
