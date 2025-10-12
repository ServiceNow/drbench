from pathlib import Path
from typing import Any, Dict

from drbench.metrics.qa_similarity_v2 import QASimilarityV2


class DistractorRecall(QASimilarityV2):
    def __init__(self, model: str):
        super().__init__(model=model)
        self.name = "distractor_recall"

    def compute(
        self,
        report_dict: Dict[str, Any],
        task_data: Dict[str, Any],
        eval_data: Dict[str, Any],
        threshold: float = 3,
    ) -> dict:
        return super().compute(
            report_dict=report_dict,
            task_data=task_data,
            eval_data=eval_data,
            insight_key="distractor",
            threshold=threshold,
        )
