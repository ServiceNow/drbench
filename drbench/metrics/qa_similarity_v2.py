import json
import re
from pathlib import Path
from typing import Any, Dict, List

from drbench.gen_agent import AIAgentManager
from drbench.metrics.base import DrBenchMetric


class QASimilarityV2(DrBenchMetric):
    def __init__(self, model: str, n: int = 1, ignore_not_answerable=False, max_retries: int = 3):
        """
        Initialize the QASimilarity metric.

        Args:
            model: The name of the model to use for scoring
            n: Number of samples to use for scoring
            max_retries: Number of attempts to parse the evaluation response
            **kwargs: Additional parameters for the model
        """
        super().__init__(name="qa_similarity_v2", model=model, n=n)
        self.model = model
        self.n = n
        self.ignore_not_answerable = ignore_not_answerable
        self.max_retries = max_retries

    def _format_claims_as_text(self, report_insights: list) -> str:
        """
        Convert report insights to a numbered list of claims.

        Args:
            report_insights: List of dictionaries with 'claim' and 'citations' keys

        Returns:
            String with numbered claims
        """
        if not report_insights:
            return "No claims found in the report."

        claims_text = ""
        for i, insight in enumerate(report_insights, 1):
            claim = insight.get("claim", "")
            claims_text += f"Insight {i}: {claim}\n"

        return claims_text.strip()

    def compute(
        self,
        report_dict: Dict[str, Any],
        task_data: Dict[str, Any],
        eval_data: Dict[str, Any],
        insight_key: str = "insight",
        threshold: float = 7,
    ) -> dict:
        """
        Compute the QA similarity scores using LLM-based evaluation.

        Args:
            report_dict: Dictionary containing 'report_text' and 'report_insights'
            task_data: Task-specific data
            eval_data: Contains 'dr_report_evaluation_qa' with questions/answers
            threshold: Threshold for the score to be considered as correct

        Returns:
            MetricResult: Standardized result with similarity scores and details
        """
        report_insights = report_dict.get("report_insights", [])
        claims_text = self._format_claims_as_text(report_insights)
        qa_eval_list = eval_data.get("dr_report_evaluation_qa", [])
        qa_eval_insights = [qa for qa in qa_eval_list if qa["qa_type"] == insight_key]

        sample_scores = []
        predictions = []
        comparisons = []

        for i, qa in enumerate(qa_eval_insights):
            question = qa["question"]
            gold_insight = qa["answer"]

            if self.ignore_not_answerable:
                # ignore if the question is not answerable or if there are no supporting files
                supporting_paths = qa.get("supporting_file_paths", []) + qa.get("supporting_urls", [])
                if len(supporting_paths) == 0:
                    continue

            # Get prediction from report

            # Score with LLM-based similarity with retry logic
            scoring_result = None
            score = 0.0
            justification = "Failed to get proper response from model"
            manager = AIAgentManager(model=self.model)

            for retry in range(self.max_retries):
                try:
                    insight_scoring_prompt_path = (
                        Path(__file__).parent.parent / "prompts" / "eval_metrics" / "insight_scoring.txt"
                    )

                    with open(insight_scoring_prompt_path, "r") as f:
                        insight_scoring_prompt_template = f.read()

                    # Format the chat setup prompt with all required variables
                    insight_scoring_prompt = insight_scoring_prompt_template.format(
                        claims_text=claims_text,
                        question=question,
                        gold_insight=gold_insight,
                    )

                    scoring_result = manager.prompt_llm(insight_scoring_prompt)
                    scoring_result_json = extract_json_from_response(scoring_result)
                    answer = scoring_result_json["answer"].lower()
                    if answer == "yes":
                        score = 1.0
                    else:
                        score = 0.0

                    justification = scoring_result_json["justification"]
                    confidence = scoring_result_json["confidence"]
                    selected_insight = scoring_result_json["selected_insight"]

                    # If we reach here, parsing was successful
                    break

                except (ValueError, IndexError, TypeError) as e:
                    if retry == self.max_retries - 1:
                        # Last retry failed, use default values
                        score = 0.0
                        justification = f"Failed to parse model response after {self.max_retries} retries: {str(e)}"
                    # Continue to next retry

            sample_scores.append(score)
            comparisons.append(
                {
                    "question": question,
                    "expected_insight": gold_insight,
                    "predicted_insight": selected_insight,
                    "expected_supporting_paths": qa.get("supporting_file_paths", []) + qa.get("supporting_urls", []),
                    "score": score,
                    "justification": justification,
                    "confidence": confidence,
                }
            )

        overall_score = sum(sample_scores) / len(sample_scores) if sample_scores else 0.0
        evaluation = {
            "score": overall_score,
            "per_question_results": [
                {
                    "question": comp["question"],
                    "expected_insight": comp["expected_insight"],
                    "predicted_insight": comp["predicted_insight"],
                    "expected_supporting_paths": comp["expected_supporting_paths"],
                    "score": comp["score"],
                    "justification": comp["justification"],
                    "confidence": comp["confidence"],
                }
                for comp in comparisons
            ],
        }
        evaluation["summary"] = ""
        for q_result in evaluation["per_question_results"]:
            evaluation["summary"] += f"#### Question: {q_result['question']}\n"
            # Add expected insight if available
            evaluation["summary"] += f"**Expected {insight_key}:** {q_result['expected_insight']}\n\n"
            if insight_key == "insight":
                evaluation["summary"] += f"**Expected Supporting Paths:** {q_result['expected_supporting_paths']}\n\n"
            evaluation["summary"] += f"**Score:** {q_result['score']:.4f}\n\n"
            evaluation["summary"] += f"**Justification:** {q_result['justification']}\n\n"
            evaluation["summary"] += f"--------------------------------\n\n"

        evaluation["metric_result"] = {"per_question_results": evaluation["per_question_results"]}
        return evaluation


def extract_json_from_response(response: str) -> List[Dict[str, Any]]:
    """Extract JSON from AI response text"""
    import re

    # Try to find JSON array or object
    json_match = re.search(r"(\[.*\]|\{.*\})", response, re.DOTALL)
    if json_match:
        try:
            return json.loads(json_match.group(1))
        except json.JSONDecodeError:
            pass

    # Try parsing the entire response
    try:
        return json.loads(response.strip())
    except json.JSONDecodeError:
        raise ValueError("Could not extract valid JSON from response")
