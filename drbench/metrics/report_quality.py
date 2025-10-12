import json
import re
import logging
from typing import Any, Dict

from drbench.agents.utils import prompt_llm
from drbench.metrics.base import DrBenchMetric

logger = logging.getLogger(__name__)


class ReportQuality(DrBenchMetric):
    def __init__(self, model: str, max_retries: int = 3):
        """
        Initialize the ReportQuality metric.

        Args:
            model: The name of the model to use for scoring
            max_retries: Number of attempts to parse the evaluation response
            **kwargs: Additional parameters for the model
        """
        super().__init__(name="report_quality", model=model)
        self.model = model
        self.max_retries = max_retries

    def _parse_evaluation_response(self, response: str, attempt: int = 1):
        """
        Parses the evaluation XML response into a structured dictionary.

        Args:
            response (str): The raw LLM output in XML-like format.
            attempt (int): Current attempt number for logging purposes.

        Returns:
            dict: A dictionary with scores and justifications per criterion.
        """

        def extract_block(tag):
            score_pattern = rf"<{tag}>\s*<score>\s*(.*?)\s*</score>\s*<justification>\s*(.*?)\s*</justification>\s*</{tag}>"
            match = re.search(score_pattern, response, re.DOTALL | re.IGNORECASE)
            if match:
                try:
                    score_str, justification = match.groups()
                    score = int(float(score_str.strip()))  # Convert to integer
                    if score > 10:
                        score = 10
                    elif score < 1:
                        score = 1
                    return {"score": score / 10.0, "justification": justification.strip()}  # Divide by 10 for final score
                except (ValueError, AttributeError) as e:
                    logger.warning(f"Error parsing score for {tag} (attempt {attempt}): {e}")
                    return {"score": 0.0, "justification": f"Failed to parse response for {tag}"}
            
            # Try alternative parsing patterns
            # Look for just score tags
            score_only_pattern = rf"<{tag}>.*?<score>\s*(.*?)\s*</score>.*?</{tag}>"
            score_match = re.search(score_only_pattern, response, re.DOTALL | re.IGNORECASE)
            if score_match:
                try:
                    score = int(float(score_match.group(1).strip()))  # Convert to integer
                    if score > 10:
                        score = 10
                    elif score < 1:
                        score = 1
                    return {"score": score / 10.0, "justification": "No justification provided"}  # Divide by 10
                except (ValueError, AttributeError):
                    pass
            
            # Look for plain number patterns
            number_pattern = rf"{tag}.*?(\d+\.?\d*)"
            number_match = re.search(number_pattern, response, re.IGNORECASE)
            if number_match:
                try:
                    score = int(float(number_match.group(1)))  # Convert to integer
                    if score > 10:
                        score = 10
                    elif score < 1:
                        score = 1
                    return {"score": score / 10.0, "justification": "Extracted from unstructured response"}  # Divide by 10
                except (ValueError, AttributeError):
                    pass
                    
            return {"score": 0.0, "justification": f"No valid response found for {tag}"}

        keys = [
            "depth_quality",
            "relevance_to_question",
            "persona_consistency",
            "coherence_conciseness",
            "contradictions",
        ]
        
        evaluation = {"metric_result": {}}
        valid_scores = 0
        
        for key in keys:
            result = extract_block(key)
            evaluation["metric_result"][key] = result
            if result["score"] > 0 or "No valid response" not in result["justification"]:
                valid_scores += 1
        
        # Calculate average score
        scores = [evaluation["metric_result"][key]["score"] for key in keys]
        evaluation["score"] = sum(scores) / len(keys) if scores else 0.0
        
        # Build summary
        evaluation["summary"] = ""
        for key in evaluation["metric_result"]:
            evaluation[
                "summary"
            ] += f"**{key}-score:** {evaluation['metric_result'][key]['score']:.4f}\n\n"
            evaluation[
                "summary"
            ] += f"**{key}-justification:** {evaluation['metric_result'][key]['justification']}\n\n\n"
            evaluation["summary"] += "--------------------------------\n\n"

        # Log parsing success rate
        if valid_scores < len(keys):
            logger.warning(f"Only parsed {valid_scores}/{len(keys)} criteria successfully (attempt {attempt})")
        
        return evaluation, valid_scores

    def compute(
        self, report_dict: Dict[str, Any], task_data: Dict[str, Any], eval_data: Dict[str, Any]
    ) -> dict:
        """
        Compute the report quality scores using LLM-based evaluation.

        Args:
            report_dict: Dictionary containing 'report_text' and 'report_insights'
            task_data: Task-specific data
            eval_data: Contains 'dr_report_evaluation_qa' with questions/answers
            **kwargs: Additional arguments

        Returns:
            MetricResult: Standardized result with quality scores and details
        """
        report_text = report_dict.get("report_text", "")
        persona = task_data["persona"]
        dr_question = task_data["dr_question"]

        prompt = f"""
        You are a Deep Research Evaluator.

        You are given:
        1. A research report.
        2. A deep research (DR) question that the report attempts to answer.
        3. A persona that represents the intended audience for the report.

        ------------------
        <persona>
        {json.dumps(persona, indent=2)}
        </persona>

        <dr_question>
        {dr_question}
        </dr_question>

        <report>
        {report_text}
        </report>
        ------------------

        ## Instructions:

        **ANALYZE THOROUGHLY**: Examine the report in detail and identify any issues, even small ones. Look for subtle problems, minor inconsistencies, areas that could be improved, or any shortcomings that might affect the quality.

        Evaluate the report according to the five criteria listed below. For **each criterion**, provide:

        - A **score between 1 and 10** (must be an integer) using the scale defined below.
        - A **detailed justification** (2–3 sentences) in **simple plain English** explaining why you gave that score, including any specific issues or strengths you identified.

        ### Scoring Scale (1-10, integers only):
        - **1-2** = Very poor, major deficiencies, completely inadequate
        - **3-4** = Poor, significant problems, below expectations
        - **5-6** = Average, meets basic requirements but has notable issues
        - **7-8** = Good, meets expectations with minor issues
        - **9-10** = Excellent, exceeds expectations with minimal or no issues

        ### Criteria:
        1. **Depth & Quality of Analysis**: Evaluate the extent to which the report delves into the details of the question, explores multiple factors, and provides a comprehensive understanding. Consider the complexity and sophistication of the analysis methods used in the report. Also, assess whether the report provides a nuanced understanding of the question, explores underlying details, or reveals unexpected findings.

        2. **Relevance To DR Question**: Assess how directly the report addresses the stated question. Evaluate how well the report aligns with the question and whether the report provides actionable recommendations or strategies that directly address the question.

        3. **Persona Consistency**: Consider how well the report aligns with the persona's values, goals, and characteristics. Evaluate whether the tone, language, and approach used in the report align with the persona's stated experience and expertise. Also, assess whether the report is engaging and relatable to the persona.

        4. **Coherence & Conciseness**: Evaluate how coherent and cohesive the report is. Assess whether the report presents information in a logical flow, makes clear connections between points, and avoids unnecessary jargon or complexity.

        5. **Degree of Contradictions**: Assess whether the report contains internal inconsistencies, logical contradictions, or conflicting statements across different insights.

        ------------------

        ## Output format:

        <evaluation>
        <depth_quality>
            <score>1–10 (integer only, based on the scoring scale above)</score>
            <justification>Give a detailed 2–3 sentence justification for your score in simple plain English, including specific issues or strengths.</justification>
        </depth_quality>

        <relevance_to_question>
            <score>1–10 (integer only, based on the scoring scale above)</score>
            <justification>Give a detailed 2–3 sentence justification for your score in simple plain English, including specific issues or strengths.</justification>
        </relevance_to_question>

        <persona_consistency>
            <score>1–10 (integer only, based on the scoring scale above)</score>
            <justification>Give a detailed 2–3 sentence justification for your score in simple plain English, including specific issues or strengths.</justification>
        </persona_consistency>

        <coherence_conciseness>
            <score>1–10 (integer only, based on the scoring scale above)</score>
            <justification>Give a detailed 2–3 sentence justification for your score in simple plain English, including specific issues or strengths.</justification>
        </coherence_conciseness>

        <contradictions>
            <score>1–10 (integer only, based on the scoring scale above)</score>
            <justification>Give a detailed 2–3 sentence justification for your score in simple plain English, including specific issues or strengths.</justification>
        </contradictions>
        </evaluation>
        """

        max_retries = self.max_retries
        min_valid_scores = 5  # Minimum number of criteria that need to be parsed successfully
        
        for attempt in range(max_retries):
            try:
                scoring_result = prompt_llm(
                    prompt,
                    model=self.model,
                    temperature=0,
                )
                
                evaluation, valid_scores = self._parse_evaluation_response(scoring_result, attempt + 1)
                
                # Check if we got enough valid scores
                if valid_scores >= min_valid_scores:
                    return evaluation
                else:
                    logger.warning(f"Insufficient valid scores ({valid_scores}/{len(['depth_quality', 'relevance_to_question', 'persona_consistency', 'coherence_conciseness', 'contradictions'])}) on attempt {attempt + 1}")
                    
            except Exception as e:
                logger.warning(f"Error in report quality evaluation (attempt {attempt + 1}): {e}")
            
            # Modify prompt for retry attempts
            if attempt < max_retries - 1:
                prompt = f"""
                You are a Deep Research Evaluator.

                You are given:
                1. A research report.
                2. A deep research (DR) question that the report attempts to answer.
                3. A persona that represents the intended audience for the report.

                ------------------
                <persona>
                {json.dumps(persona, indent=2)}
                </persona>

                <dr_question>
                {dr_question}
                </dr_question>

                <report>
                {report_text}
                </report>
                ------------------

                IMPORTANT: You MUST respond in the EXACT format shown below. Do not add any extra text.

                **ANALYZE THOROUGHLY**: Find any issues, even small ones. Look for problems, inconsistencies, or areas for improvement.

                Evaluate the report on these 5 criteria (score each from 1 to 10 as integers):
                1. Depth & Quality of Analysis
                2. Relevance To DR Question  
                3. Persona Consistency
                4. Coherence & Conciseness
                5. Degree of Contradictions

                **Scoring Scale**: 1-2=Very poor, 3-4=Poor, 5-6=Average, 7-8=Good, 9-10=Excellent

                Format your response EXACTLY as:

                <evaluation>
                <depth_quality>
                <score>8</score>
                <justification>Your detailed justification here with specific issues or strengths identified</justification>
                </depth_quality>
                <relevance_to_question>
                <score>7</score>
                <justification>Your detailed justification here with specific issues or strengths identified</justification>
                </relevance_to_question>
                <persona_consistency>
                <score>6</score>
                <justification>Your detailed justification here with specific issues or strengths identified</justification>
                </persona_consistency>
                <coherence_conciseness>
                <score>9</score>
                <justification>Your detailed justification here with specific issues or strengths identified</justification>
                </coherence_conciseness>
                <contradictions>
                <score>8</score>
                <justification>Your detailed justification here with specific issues or strengths identified</justification>
                </contradictions>
                </evaluation>
                """

        # If all retries failed, return a default evaluation
        logger.error(f"Failed to get valid report quality evaluation after {max_retries} attempts")
        
        keys = [
            "depth_quality",
            "relevance_to_question", 
            "persona_consistency",
            "coherence_conciseness",
            "contradictions",
        ]
        
        default_evaluation = {"metric_result": {}}
        for key in keys:
            default_evaluation["metric_result"][key] = {
                "score": 0.5,  # Neutral score when evaluation fails (equivalent to 5/10)
                "justification": "Failed to evaluate due to parsing errors"
            }
        
        default_evaluation["score"] = 0.5
        default_evaluation["summary"] = ""
        for key in default_evaluation["metric_result"]:
            default_evaluation[
                "summary"
            ] += f"**{key}-score:** {default_evaluation['metric_result'][key]['score']:.4f}\n\n"
            default_evaluation[
                "summary"
            ] += f"**{key}-justification:** {default_evaluation['metric_result'][key]['justification']}\n\n\n"
            default_evaluation["summary"] += "--------------------------------\n\n"

        return default_evaluation
