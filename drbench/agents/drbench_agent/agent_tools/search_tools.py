import json
import logging
from datetime import datetime
from typing import Any, Dict

import requests

from .base import ResearchContext, Tool

logger = logging.getLogger(__name__)


class InternetSearchTool(Tool):
    """Tool for searching the internet and fetching URL content using Serper or similar service"""

    @property
    def purpose(self) -> str:
        return """External market research, competitive intelligence, and public data analysis. 
        IDEAL FOR: Market trends, competitor analysis, industry reports, public research papers, news articles, regulatory information, and technology comparisons.
        USE WHEN: Research requires public/external sources, competitor benchmarking, market validation, industry context, or recent developments.
        PARAMETERS: query (specific search terms work best - e.g., 'AI market size 2024', 'competitor pricing strategies', 'regulatory changes fintech')
        OUTPUTS: Search results with URLs, snippets, and relevant content that gets automatically processed and stored for synthesis."""

    def __init__(self, api_key: str, service: str = "serper", vector_store: Any = None, content_processor: Any = None):
        self.api_key = api_key
        self.service = service
        self.base_url = "https://google.serper.dev/search" if service == "serper" else None
        self.vector_store = vector_store
        self.content_processor = content_processor


    def execute(self, query: str, context: ResearchContext) -> Dict[str, Any]:
        """Execute internet search with URL content fetching and standardized output"""

        if not self.api_key:
            return self.create_error_output("internet_search", query, "API key not provided for internet search")

        headers = {"X-API-KEY": self.api_key, "Content-Type": "application/json"}
        payload = json.dumps({"q": query, "num": 10})  # Number of results

        # Debug logging for 400 error investigation
        logger.debug(f"🔍 InternetSearchTool Debug Info:")
        logger.debug(f"  URL: {self.base_url}")
        logger.debug(f"  Query: {repr(query)}")
        logger.debug(f"  Query length: {len(query)} chars")
        logger.debug(f"  Query bytes: {len(query.encode('utf-8'))} bytes")
        logger.debug(f"  Headers: {headers}")
        logger.debug(f"  Payload: {payload}")
        logger.debug(f"  Payload length: {len(payload)} bytes")

        try:
            response = requests.post(self.base_url, headers=headers, data=payload, timeout=30)
            
            # Log response details for debugging
            logger.debug(f"  Response status: {response.status_code}")
            logger.debug(f"  Response headers: {dict(response.headers)}")
            
            response.raise_for_status()
            results = response.json()

            # Extract key information
            search_results = []
            for result in results.get("organic", []):
                search_results.append(
                    {"title": result.get("title"), "link": result.get("link"), "snippet": result.get("snippet")}
                )

            # Include additional info if available
            additional_info = {}
            if "answerBox" in results:
                additional_info["answer_box"] = results["answerBox"]
            if "knowledgeGraph" in results:
                additional_info["knowledge_graph"] = results["knowledgeGraph"]

            # Enhanced: Fetch content from top URLs if content processor is available
            fetched_content = []
            content_stored_count = 0
            
            if self.content_processor and search_results:
                logger.info(f"🌐 Fetching content from top {min(5, len(search_results))} search results...")
                
                for i, result in enumerate(search_results[:5]):  # Fetch top 5 URLs
                    url = result.get("link")
                    if url:
                        try:
                            # Use content processor to fetch and store URL content
                            content_result = self.content_processor.process_url(
                                url=url,
                                query_context=f"Search query: {query}"
                            )
                            
                            if content_result.get("success"):
                                fetched_content.append({
                                    "url": url,
                                    "title": result.get("title"),
                                    "content_length": content_result.get("content_length", 0),
                                    "stored_in_vector": content_result.get("stored_in_vector", False),
                                    "doc_id": content_result.get("doc_id"),
                                    "file_path": content_result.get("file_path")
                                })
                                
                                if content_result.get("stored_in_vector"):
                                    content_stored_count += 1
                                    
                                # Also store search result metadata linking to content
                                if self.vector_store:
                                    search_doc_id = self.vector_store.store_document(
                                        content=f"Search Result for '{query}'\n\nTitle: {result.get('title')}\nURL: {url}\nSnippet: {result.get('snippet')}\n\nFull content stored separately with doc_id: {content_result.get('doc_id')}",
                                        metadata={
                                            "type": "search_result",
                                            "query": query,
                                            "url": url,
                                            "title": result.get("title"),
                                            "snippet": result.get("snippet"),
                                            "search_rank": i + 1,
                                            "linked_content_doc_id": content_result.get("doc_id"),
                                            "timestamp": datetime.now().isoformat()
                                        }
                                    )
                            else:
                                fetched_content.append({
                                    "url": url,
                                    "title": result.get("title"),
                                    "error": content_result.get("error"),
                                    "stored_in_vector": False
                                })
                                
                        except Exception as e:
                            fetched_content.append({
                                "url": url,
                                "title": result.get("title"),
                                "error": str(e),
                                "stored_in_vector": False
                            })
                            
                logger.info(f"✅ Fetched content from {len(fetched_content)} URLs, {content_stored_count} stored in vector store")

            return self.create_success_output(
                tool_name="internet_search",
                query=query,
                results=search_results,
                data_retrieved=len(search_results) > 0,
                total_results=len(search_results),
                additional_info=additional_info,
                raw_response=results,  # Keep raw response for debugging
                # Enhanced fields
                fetched_content=fetched_content,
                urls_processed=len(fetched_content),
                content_stored_in_vector=content_stored_count,
                stored_in_vector=content_stored_count > 0
            )

        except requests.exceptions.RequestException as e:
            # Enhanced error logging for 400 errors
            error_details = {
                "error_type": type(e).__name__,
                "error_message": str(e),
                "query": repr(query),
                "url": self.base_url,
                "headers": headers,
                "payload": payload
            }
            
            # If we have a response, log its details
            if hasattr(e, 'response') and e.response is not None:
                try:
                    error_details.update({
                        "response_status": e.response.status_code,
                        "response_headers": dict(e.response.headers),
                        "response_text": e.response.text[:1000]  # First 1000 chars
                    })
                    logger.error(f"🚨 HTTP Error {e.response.status_code}: {error_details}")
                    
                    # Special handling for 400 errors
                    if e.response.status_code == 400:
                        logger.error(f"🔴 400 BAD REQUEST DETAILS:")
                        logger.error(f"  Full response text: {e.response.text}")
                        logger.error(f"  Request payload that caused error: {payload}")
                        logger.error(f"  Original query: {repr(query)}")
                        
                except Exception as log_err:
                    logger.error(f"Failed to log response details: {log_err}")
            else:
                logger.error(f"🚨 Network Error (no response): {error_details}")
            
            return self.create_error_output("internet_search", query, f"Network error: {str(e)}")
        except json.JSONDecodeError as e:
            logger.error(f"🚨 JSON Decode Error: {str(e)} - Response text: {getattr(response, 'text', 'No response text')}")
            return self.create_error_output("internet_search", query, f"Invalid JSON response: {str(e)}")
        except Exception as e:
            logger.error(f"🚨 Unexpected Error: {type(e).__name__}: {str(e)}")
            return self.create_error_output("internet_search", query, f"Search failed: {str(e)}")
