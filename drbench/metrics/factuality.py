from typing import Any, Dict, List
from pathlib import Path
import json, re

from drbench.metrics.base import DrBenchMetric
from drbench.metrics.utils.source_reader import SourceReader
from drbench.metrics.utils.semantic_retriever import SemanticRetriever
from drbench.agents.utils import prompt_llm


class ClaimFactuality(DrBenchMetric):
    def __init__(
        self,
        model: str,
        chunk_size: int = 1000,
        top_k_chunks: int = 3,
        embedding_model: str = "text-embedding-3-small",
    ):
        """
        Initialize the ClaimFactuality metric.

        Args:
            model: The name of the model to use for scoring
            chunk_size: Size of text chunks for semantic retrieval system
            top_k_chunks: Number of top chunks to retrieve for each claim
            embedding_model: OpenAI embedding model to use
        """
        super().__init__(
            name="factuality",
            model=model,
            chunk_size=chunk_size,
            top_k_chunks=top_k_chunks,
            embedding_model=embedding_model,
        )
        self.model = model
        self.source_reader = SourceReader()
        self.semantic_retriever = SemanticRetriever(
            chunk_size=chunk_size, embedding_model=embedding_model
        )
        self.top_k_chunks = top_k_chunks

    def _extract_links(self, text: str) -> List[str]:
        """
        Extracts all URLs from a given text string.

        Args:
            text (str): The input text containing URLs.

        Returns:
            List[str]: A list of extracted URLs.
        """
        url_pattern = re.compile(r'(https?://[^\s<>"]+|www\.[^\s<>"]+)', re.IGNORECASE)
        return url_pattern.findall(text)

    def compute(
        self, report_dict: Dict[str, Any], task_data: Dict[str, Any], eval_data: Dict[str, Any]
    ) -> dict:
        """
        Compute factuality scores using RAG-based evaluation.

        Args:
            report_dict: Dictionary containing 'report_text' and 'report_insights'
            task_data: Task-specific data including source documents
            eval_data: Evaluation data including supporting URLs

        Returns:
            Dict: Standardized result with claim-based factuality scores
        """
        report_text = report_dict.get("report_text", "")
        supporting_docs = []
        supporting_urls = []

        qa_eval_list = eval_data.get("dr_report_evaluation_qa", [])
        for qa in qa_eval_list:
            for url in qa.get("supporting_urls", []):
                supporting_urls.append(url)

        env_files = task_data.get("env_files", [])
        for env_file in env_files:
            supporting_docs.append("drbench/data/" + env_file["source"])

        # Load content from supporting documents and URLs
        source_documents = []

        # Load file contents
        for doc_path in supporting_docs:
            result = self.source_reader.parse_file(Path(doc_path))
            if result is not None:
                title, content = result
                source_documents.append(
                    {
                        "title": title,
                        "content": content,
                        "source_type": "file",
                        "source_path": doc_path,
                    }
                )

        # Load URL contents
        for url in supporting_urls:
            result = self.source_reader.parse_website(url)
            if result is not None:
                title, content = result
                source_documents.append(
                    {
                        "title": title,
                        "content": content,
                        "source_type": "url",
                        "source_path": url,
                    }
                )

        citation_links = self._extract_links(report_text)
        for url in citation_links:
            result = self.source_reader.parse_website(url)
            if result is not None:
                title, content = result
                source_documents.append(
                    {
                        "title": title,
                        "content": content,
                        "source_type": "url",
                        "source_path": url,
                    }
                )

        if not source_documents:
            return {
                "factual_claims": [],
                "unfactual_claims": [],
                "factuality_percentage": 0.0,
                "total_claims": 0,
            }

        # Initialize semantic retriever with source documents
        self.semantic_retriever.add_documents(source_documents)

        # Break down report text into atomic claims
        atomic_claims_prompt = f"""
        Please break down the following report text into atomic claims. Each atomic claim should be:
        1. A single, specific statement
        2. Independent and self-contained
        3. Atomic claim should include some information and facts, if the claim is a conclusion based on previous facts, ignore them
        
        Report text:
        {report_text}
        
        Please return the atomic claims as a JSON list of strings. For example:
        ["The company's revenue increased by 15% in Q3 2023", "The new product launch contributed to the growth", "Customer satisfaction scores improved to 4.2 out of 5"]
        
        Return only the JSON list, no additional text.
        """

        atomic_claims_response = prompt_llm(atomic_claims_prompt, self.model)

        # Parse JSON response
        try:
            atomic_claims = json.loads(atomic_claims_response.strip())
            if not isinstance(atomic_claims, list):
                atomic_claims = []
        except json.JSONDecodeError:
            # Fallback: try to extract JSON from response if there's extra text
            try:
                start_idx = atomic_claims_response.find("[")
                end_idx = atomic_claims_response.rfind("]") + 1
                if start_idx != -1 and end_idx != 0:
                    json_part = atomic_claims_response[start_idx:end_idx]
                    atomic_claims = json.loads(json_part)
                    if not isinstance(atomic_claims, list):
                        atomic_claims = []
                else:
                    atomic_claims = []
            except json.JSONDecodeError:
                atomic_claims = []

        zero_dict = {
            "factual_claims": [],
            "unfactual_claims": atomic_claims,
            "factuality_percentage": 0.0,
            "total_claims": len(atomic_claims),
            "score": 0.0,
            "summary": "no citations or insights found",
            "metric_result": {
                "factual_claims": [],
                "unfactual_claims": atomic_claims,
                "factuality_percentage": 0.0,
                "total_claims": len(atomic_claims),
            },
        }

        if not atomic_claims:
            return zero_dict

        # Check factuality of each atomic claim using RAG
        factual_claims = []
        unfactual_claims = []

        for claim in atomic_claims:
            # Retrieve relevant chunks for this claim
            relevant_chunks = self.semantic_retriever.retrieve_relevant_chunks(
                claim, self.top_k_chunks
            )

            if not relevant_chunks:
                # No relevant chunks found, consider unfactual
                unfactual_claims.append(claim)
                continue

            # Prepare context from relevant chunks
            context_parts = []
            for chunk in relevant_chunks:
                context_parts.append(
                    f"Source: {chunk['source']}\nContent: {chunk['text'][:500]}..."
                )

            context = "\n\n---\n\n".join(context_parts)

            factuality_prompt = f"""
            Given the following relevant source materials and an atomic claim, determine if the claim is factually supported by the sources.
            
            Relevant Source Materials:
            {context}
            
            Atomic Claim: {claim}
            
            Please analyze if this claim is:
            1. Directly supported by the source materials
            2. Can be reasonably inferred from the source materials
            3. Contradicted by the source materials
            4. Not mentioned or supported by the source materials
            
            Respond with either "FACTUAL" if the claim is supported (directly or through reasonable inference) or "UNFACTUAL" if it is contradicted or not supported.
            Then provide a brief explanation.
            
            Format your response as:
            VERDICT: [FACTUAL/UNFACTUAL]
            EXPLANATION: [brief explanation]
            """

            factuality_response = prompt_llm(factuality_prompt, self.model)

            # Parse response
            if "VERDICT: FACTUAL" in factuality_response.upper():
                factual_claims.append(claim)
            else:
                unfactual_claims.append(claim)

        # Calculate factuality percentage
        total_claims = len(atomic_claims)
        factual_count = len(factual_claims)
        factuality_percentage = (
            (factual_count / total_claims * 100) if total_claims > 0 else 0.0
        )

        evaluation = {
            "factual_claims": factual_claims,
            "unfactual_claims": unfactual_claims,
            "factuality_percentage": factuality_percentage,
            "total_claims": total_claims,
        }
        evaluation["metric_result"] = {
            "factual_claims": factual_claims,
            "unfactual_claims": unfactual_claims,
            "factuality_percentage": factuality_percentage,
            "total_claims": total_claims,
        }
        evaluation["score"] = factuality_percentage / 100.0
        evaluation["summary"] = ""
        evaluation["summary"] += f"**Factuality:** {factuality_percentage:.4f}\n\n"
        evaluation["summary"] += f"**Factual Claims:** {factual_claims}\n\n"
        evaluation["summary"] += f"**Unfactual Claims:** {unfactual_claims}\n\n"
        evaluation["summary"] += f"**Total Claims:** {total_claims}\n\n"
        evaluation["summary"] += f"--------------------------------\n\n"
        return evaluation
