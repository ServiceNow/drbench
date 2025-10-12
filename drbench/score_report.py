import datetime
import json
import logging
import os
import re
import time
import dotenv

# Load environment variables
dotenv.load_dotenv()

# Suppress specific LiteLLM warning
logging.getLogger("LiteLLM").setLevel(logging.ERROR)

from typing import Any, Dict, List, Optional

from drbench import task_loader
from drbench.agents.utils import (
    break_report_to_insights,
    get_factuality_verdict_multi,
    prompt_llm,
)
from drbench.metrics import get_metric

# Truncate report text to 60000 characters if necessary
MAX_REPORT_LENGTH = 60000


def score_report(
    predicted_report_text: str = None,
    task_config: Dict[str, Any] = None,
    eval_config: Dict[str, Any] = None,
    metrics: List[str] = ["insights_recall"],
    savedir: str = None,
    verbose: bool = True,
    upload_scores: bool = False,
    agent_tag: str = None,
    predicted_report_dict: Dict[str, Any] = None,
    include_per_insight_scores: bool = True,
    model="gpt-4o-mini",
    predicted_report=None,
    task=None,
    timing_dict=None,
) -> dict:
    """
    Evaluate a report with all configured metrics.
    """
    scoring_start_time = time.perf_counter()
    if predicted_report is not None:
        if isinstance(predicted_report, str):
            predicted_report_text = predicted_report
        elif isinstance(predicted_report, dict):
            predicted_report_dict = predicted_report
        else:
            raise ValueError("predicted_report must be a string or a dictionary")
    if task is not None:
        task_config = task.get_task_config()
        eval_config = task.get_eval_config()

    if upload_scores is True and agent_tag is None:
        raise ValueError("agent_tag is required when upload_scores is True - just for the leaderboard")
    if upload_scores is True and savedir is None:
        raise ValueError("savedir is required when upload_scores is True")

    if predicted_report_text is not None:
        if len(predicted_report_text) > MAX_REPORT_LENGTH:
            if verbose:
                print(
                    f"⚠️  WARNING: Report text ({len(predicted_report_text)} characters) exceeds {MAX_REPORT_LENGTH} character limit. Using only the first {MAX_REPORT_LENGTH} characters."
                )
            predicted_report_text = predicted_report_text[:MAX_REPORT_LENGTH]

    # Prepare report dictionary for metrics
    if predicted_report_dict is None and predicted_report_text is not None:
        # Extract insights and citations from the report text
        if verbose:
            print("Extracting insights and citations from report text...")
        report_insights = break_report_to_insights(predicted_report_text, model=model)

        predicted_report_dict = {
            "report_insights": report_insights,
        }
    elif predicted_report_dict is not None:
        # Validate the format of the provided dictionary
        is_valid_format = True

        # Check if it's a dictionary
        if not isinstance(predicted_report_dict, dict):
            is_valid_format = False
            if verbose:
                print("⚠️  WARNING: predicted_report_dict must be a dictionary. Using break_report_to_insights instead.")

        # Check if report_insights exists and is a list
        elif "report_insights" not in predicted_report_dict:
            is_valid_format = False
            if verbose:
                print(
                    "⚠️  WARNING: predicted_report_dict missing 'report_insights' key. Using break_report_to_insights instead."
                )

        elif not isinstance(predicted_report_dict["report_insights"], list):
            is_valid_format = False
            if verbose:
                print("⚠️  WARNING: 'report_insights' must be a list. Using break_report_to_insights instead.")

        # Check if insights have the expected structure (claim and citations keys)
        elif predicted_report_dict["report_insights"]:  # Only check if list is not empty
            sample_insight = predicted_report_dict["report_insights"][0]
            if (
                not isinstance(sample_insight, dict)
                or "claim" not in sample_insight
                or "citations" not in sample_insight
            ):
                is_valid_format = False
                if verbose:
                    print(
                        "⚠️  WARNING: Invalid insight format. Each insight must be a dict with 'claim' and 'citations' keys. Using break_report_to_insights instead."
                    )

        if not is_valid_format and predicted_report_text is not None:
            # Fall back to extracting insights if report dict not properly structured
            if verbose:
                print("Extracting insights and citations from report text...")
            report_insights = break_report_to_insights(predicted_report_text)
            predicted_report_dict = {
                "report_text": predicted_report_text,
                "report_insights": report_insights,
            }
        elif is_valid_format:
            if verbose:
                print(
                    f"Using provided insights dictionary with {len(predicted_report_dict['report_insights'])} insights."
                )
        else:
            raise ValueError("No report text passed and insights dictionary not properly structured.")

    else:
        raise ValueError("Neither report text or insights are provided to scoring function.")

    # Run each metric
    score_dict = {}
    metric_results = []
    for metric_name in metrics:
        if verbose:
            print(f"Computing {metric_name}...")

        metric = get_metric(metric_name)
        metric_result = metric.compute(
            report_dict=predicted_report_dict,
            task_data=task_config,
            eval_data=eval_config,
        )

        score_dict[metric_name] = metric_result["score"]
        metric_result["name"] = metric_name
        metric_results.append(metric_result)

        if verbose:
            print(f"  {metric_name}: {score_dict[metric_name]:.4f}")

    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Compute per-insight scores if requested
    per_insight_scores = []
    if include_per_insight_scores:
        # Get first 10 atomic insights from report_dict
        report_insights = predicted_report_dict.get("report_insights", [])
        selected_insights = report_insights[:10]  # Limit to first 10 insights

        if selected_insights and verbose:
            print("Computing per-insight factuality and recall scores...")

        # Check if factuality results are already available from metrics
        factuality_results = None
        for metric_result in metric_results:
            if metric_result.get("name") in ["factuality_v2", "factuality"]:
                factuality_results = metric_result.get("metric_result", {})
                break

        # If factuality was computed, use those results; otherwise compute separately
        if factuality_results and "factual_claims" in factuality_results and "unfactual_claims" in factuality_results:
            if verbose:
                print("Using existing factuality results from factuality metric...")

            # Create a mapping from insights to factuality results using detailed_factuality
            factuality_details_map = {}
            if "detailed_factuality" in factuality_results:
                for detail in factuality_results["detailed_factuality"]:
                    insight_text = detail.get("answer", "")
                    factuality_details_map[insight_text] = {
                        "is_factual": detail.get("is_factual", False),
                        "explanation": detail.get("explanation", "No explanation available"),
                        "citations": detail.get("citations", []),
                    }

            # Fallback to basic factual/unfactual lists if detailed_factuality not available
            factual_claims = set(factuality_results.get("factual_claims", []))
            unfactual_claims = set(factuality_results.get("unfactual_claims", []))

            for insight_data in selected_insights:
                insight_text = insight_data.get("claim", "")
                citations = insight_data.get("citations", [])

                # Try to get detailed factuality information first
                if insight_text in factuality_details_map:
                    factuality_detail = factuality_details_map[insight_text]
                    is_factual = factuality_detail["is_factual"]
                    justification = factuality_detail["explanation"]
                # Fallback to basic factual/unfactual classification
                elif insight_text in factual_claims:
                    is_factual = True
                    justification = "Verified as factual by the factuality metric"
                elif insight_text in unfactual_claims:
                    is_factual = False
                    justification = "Identified as unfactual by the factuality metric"
                else:
                    # This insight wasn't evaluated in the main metric, compute separately
                    env_files = task_loader.from_task_config_to_env_files(task_config)
                    factuality_result = get_factuality_verdict_multi(
                        insight_text,
                        citations,
                        file_list=env_files,
                        model="gpt-4o-mini",
                    )
                    is_factual = factuality_result["is_factual"]
                    justification = factuality_result["explanation"]

                per_insight_scores.append(
                    {
                        "predicted_insight": insight_text,
                        "predicted_citations": citations,
                        "factuality": {
                            "is_factual": is_factual,
                            "justification": justification,
                        },
                        "recall": {
                            "matched_gt_insight": None,  # Will be filled below
                            "justification": "",  # Will be filled below
                        },
                    }
                )
        else:
            # Compute factuality for each insight separately
            if verbose:
                print("Computing factuality separately for each insight...")

            env_files = task_loader.from_task_config_to_env_files(task_config)

            for insight_data in selected_insights:
                insight_text = insight_data.get("claim", "")
                citations = insight_data.get("citations", [])

                # Get factuality verdict
                factuality_result = get_factuality_verdict_multi(
                    insight_text, citations, file_list=env_files, model="gpt-4o-mini"
                )

                per_insight_scores.append(
                    {
                        "predicted_insight": insight_text,
                        "predicted_citations": citations,
                        "factuality": {
                            "is_factual": factuality_result["is_factual"],
                            "justification": factuality_result["explanation"],
                        },
                        "recall": {
                            "matched_gt_insight": None,  # Will be filled below
                            "justification": "",  # Will be filled below
                        },
                    }
                )

        # Get ground truth insights for recall matching
        qa_eval_list = eval_config.get("dr_report_evaluation_qa", [])
        gt_insights = [qa["answer"] for qa in qa_eval_list if qa.get("answer") != "Not answerable"]

        # Match predicted insights with ground truth using LLM
        if selected_insights and gt_insights:
            predicted_insights_text = [insight_data.get("claim", "") for insight_data in selected_insights]

            recall_matching_prompt = f"""
            You are given a list of predicted atomic insights and a list of ground truth insights. 
            For each predicted insight, determine if it matches any ground truth insight and provide justification.

            Predicted Insights:
            {json.dumps(predicted_insights_text, indent=2)}

            Ground Truth Insights:
            {json.dumps(gt_insights, indent=2)}

            For each predicted insight, return a JSON object with:
            - "predicted_insight": the predicted insight text
            - "matched_golden_insight": the matching ground truth insight (or null if no match)
            - "justification": explanation of the match or why no match was found

            Return ONLY a valid JSON array with {len(predicted_insights_text)} objects, one for each predicted insight.
            Insights should convey the same core information to be considered a match, no need to have exact wording.
            """

            # Retry mechanism for recall matching
            max_retries = 5
            retry_delay = 1  # Initial delay in seconds

            for attempt in range(max_retries):
                try:
                    if verbose and attempt > 0:
                        print(f"Retrying recall matching (attempt {attempt + 1}/{max_retries})...")

                    recall_response = prompt_llm(recall_matching_prompt, "gpt-4o-mini", temperature=0)

                    # Extract JSON from response using regex to handle various formats
                    response_text = recall_response.strip()

                    # Try to find JSON array in the response using regex
                    # Look for content between [ and ] that might be wrapped in code blocks
                    json_match = re.search(r"```(?:json)?\s*(\[.*?\])\s*```", response_text, re.DOTALL)
                    if json_match:
                        # Found JSON in code blocks
                        json_text = json_match.group(1)
                    else:
                        # Try to find JSON array without code blocks
                        json_match = re.search(r"(\[.*?\])", response_text, re.DOTALL)
                        if json_match:
                            json_text = json_match.group(1)
                        else:
                            # Fallback: use the entire response
                            json_text = response_text

                    recall_matches = json.loads(json_text.strip())

                    # Validate that we got the expected number of matches
                    if len(recall_matches) != len(predicted_insights_text):
                        raise ValueError(
                            f"Expected {len(predicted_insights_text)} recall matches, got {len(recall_matches)}"
                        )

                    # Update per_insight_scores with recall information
                    for i, recall_match in enumerate(recall_matches):
                        if i < len(per_insight_scores):
                            per_insight_scores[i]["recall"]["matched_gt_insight"] = recall_match.get(
                                "matched_golden_insight"
                            )
                            per_insight_scores[i]["recall"]["justification"] = recall_match.get("justification", "")

                    # Success - break out of retry loop
                    break

                except (json.JSONDecodeError, ValueError, Exception) as e:
                    if verbose:
                        print(f"Attempt {attempt + 1} failed: {e}")

                    if attempt == max_retries - 1:  # Last attempt
                        if verbose:
                            print(f"Warning: All {max_retries} attempts failed for recall matching: {e}")
                        # Fill with default values if all attempts fail
                        for insight_score in per_insight_scores:
                            insight_score["recall"][
                                "justification"
                            ] = f"Failed to compute recall matching after {max_retries} attempts: {str(e)}"
                    else:
                        # Wait before retrying (exponential backoff)
                        time.sleep(retry_delay)
                        retry_delay *= 2  # Double the delay for next attempt

    if savedir:
        os.makedirs(savedir, exist_ok=True)
        print(f"Saved in {savedir}")
        # Save Markdown Report
        with open(os.path.join(savedir, "evaluation_report.md"), "w") as f:
            f.write("# 📊 DrBench Evaluation Report\n\n")
            f.write(f"**Timestamp:** {timestamp}\n\n")
            f.write(f"**Task ID:** `{task_config['name']}`\n\n")
            f.write(f"**Question:** {task_config['dr_question']}\n\n")
            if agent_tag:
                f.write(f"**Agent Tag:** {agent_tag}\n\n")
            f.write(f"**Generated Report:**\n```\n{predicted_report_text}\n```\n\n")
            f.write(f"**Overall Scores:** {score_dict}\n\n")

            # Add report dictionary details
            f.write("## 📋 Report Dictionary\n\n")
            f.write("**Extracted Insights with Citations:**\n\n")
            report_insights = predicted_report_dict.get("report_insights", [])
            if report_insights:
                for idx, insight in enumerate(report_insights, 1):
                    f.write(f"**Insight {idx}:**\n")
                    f.write(f"- **Claim:** {insight.get('claim', 'N/A')}\n")
                    f.write(f"- **Citations:** {insight.get('citations', [])}\n\n")
            else:
                f.write("No insights extracted.\n\n")

            # Add per-insight scores if computed
            if per_insight_scores:
                f.write("## 🔍 Per-Insight Analysis\n\n")
                f.write("**Individual Insight Scores (Limited to first 10 insights):**\n\n")
                for idx, insight_score in enumerate(per_insight_scores, 1):
                    f.write(f"### Insight {idx}\n\n")
                    f.write(f"**Predicted Insight:** {insight_score.get('predicted_insight', 'N/A')}\n\n")
                    f.write(f"**Predicted Citations:** {insight_score.get('predicted_citations', [])}\n\n")

                    # Factuality section
                    factuality = insight_score.get("factuality", {})
                    f.write(f"**Factuality:**\n")
                    f.write(f"- **Is Factual:** {'✅ Yes' if factuality.get('is_factual', False) else '❌ No'}\n")
                    f.write(f"- **Justification:** {factuality.get('justification', 'N/A')}\n\n")

                    # Recall section
                    recall = insight_score.get("recall", {})
                    f.write(f"**Recall:**\n")
                    matched_gt = recall.get("matched_gt_insight")
                    if matched_gt:
                        f.write(f"- **Matched Ground Truth:** {matched_gt}\n")
                        f.write(f"- **Match Status:** ✅ Matched\n")
                    else:
                        f.write(f"- **Match Status:** ❌ No Match\n")
                    f.write(f"- **Justification:** {recall.get('justification', 'N/A')}\n\n")
                    f.write("---\n\n")

            # Add detailed per-question results for metrics that provide them
            for metric_idx, metric_result in enumerate(metric_results):
                metric_name = metric_result["name"]
                f.write(f"## Metric {metric_idx}: {metric_name}\n\n")
                f.write(f"**Score:** {metric_result['score']:.4f}\n\n")
                f.write(f"**Summary:** {metric_result['summary']}\n\n")

                f.write("---\n\n")

        scoring_end_time = time.perf_counter()
        scoring_time = scoring_end_time - scoring_start_time
        # Save JSON Report
        with open(os.path.join(savedir, "evaluation_report.json"), "w") as f:
            full_report = {
                "task_id": task_config["task_id"],
                "question": task_config["dr_question"],
                "generated_report": predicted_report_text,
                "report_dict": predicted_report_dict,  # Add the atomic insights with citations
                "overall_scores": score_dict,
                "metrics_details": [],
                "timestamp": timestamp,
            }
            if agent_tag:
                full_report["agent_tag"] = agent_tag

            # Add per-insight scoring if computed
            if per_insight_scores:
                full_report["per_predicted_insight_scores"] = per_insight_scores

            if timing_dict is not None:
                total_time = timing_dict["setup_time"] + timing_dict["generate_report_time"] + scoring_time
                full_report["timing"] = {
                    "setup_time": timing_dict["setup_time"],
                    "generate_report_time": timing_dict["generate_report_time"],
                    "score_report_time": scoring_time,
                    "total_time": total_time,
                }

            # Add detailed results for each metric
            for metric_result in metric_results:
                metric_detail = {
                    "name": metric_result["name"],
                    "score": metric_result["score"],
                }

                metric_detail.update(metric_result["metric_result"])

                full_report["metrics_details"].append(metric_detail)

            json.dump(full_report, f, indent=4)

    # add other info to score_dict
    score_dict["predicted_report_text"] = predicted_report_text
    score_dict["task_id"] = task_config["task_id"]
    score_dict["question"] = task_config["dr_question"]

    if upload_scores:
        if verbose:
            print("\nUploading Results to the Cloud...")
        # upload to dropbox
        upload_to_dropbox(savedir)
        if verbose:
            print(f"\nSUCCESS:Uploaded {savedir} to the Cloud!")

    return score_dict
