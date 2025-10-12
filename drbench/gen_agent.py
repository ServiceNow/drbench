# suppress warnings
import warnings

warnings.filterwarnings("ignore")

# import libraries
import argparse
import os
import textwrap
from typing import Any, Dict, List, Optional

from openai import OpenAI
from together import Together

# Import centralized configuration
from drbench import config

# Available AI Models Configuration
AVAILABLE_SERVICES = ["vllm", "together", "openai"]
AVAILABLE_MODELS = [
    "meta-llama/Meta-Llama-3-8B-Instruct-Lite",
    "meta-llama/Llama-3.3-70B-Instruct-Turbo",
    "meta-llama/Meta-Llama-3-70B-Instruct-Lite",
    "meta-llama/Meta-Llama-3.1-8B-Instruct-Turbo",
    "meta-llama/Meta-Llama-3.1-70B-Instruct-Turbo",
    "neuralmagic/Meta-Llama-3.1-405B-Instruct-FP8",
    "mistralai/Mixtral-8x7B-Instruct-v0.1",
    "mistralai/Mistral-7B-Instruct-v0.1",
    "gpt-4o-mini",
    "gpt-4o",
]

SERVICE_TO_MODELS = {
    "vllm": ["neuralmagic/Meta-Llama-3.1-405B-Instruct-FP8"],
    "together": [
        "meta-llama/Meta-Llama-3-8B-Instruct-Lite",
        "meta-llama/Llama-3.3-70B-Instruct-Turbo",
    ],
    "openai": ["gpt-4o-mini", "gpt-4o"],
}


class AIAgentManager:
    """Manager class for AI agent operations"""

    def __init__(
        self,
        api_key: Optional[str] = None,
        api_url: Optional[str] = None,
        model: str = "meta-llama/Meta-Llama-3-8B-Instruct-Lite",
        max_tokens: int = 1000,
        temperature: float = 0.7,
        with_linebreak: bool = False,
    ):
        if model in SERVICE_TO_MODELS["vllm"]:
            self.service = "vllm"
        elif model in SERVICE_TO_MODELS["together"]:
            self.service = "together"
        elif model in SERVICE_TO_MODELS["openai"]:
            self.service = "openai"
        else:
            raise ValueError(f"Invalid model: {model}")

        self.client = None
        self.model = model
        self.max_tokens = max_tokens
        self.temperature = temperature
        self.with_linebreak = with_linebreak
        self.get_api_key_from_env(api_key, api_url)
        self.initialize_client()

    def get_api_key_from_env(self, api_key, api_url):
        """Get the API key from the environment"""
        if self.service == "vllm":
            self.api_url = api_url or config.VLLM_API_URL
            self.api_key = api_key or config.VLLM_API_KEY
        elif self.service == "together":
            self.api_key = api_key or config.TOGETHER_API_KEY
        elif self.service == "openai":
            self.api_key = api_key or config.OPENAI_API_KEY

    def initialize_client(self):
        if not self.api_key:
            raise ValueError("No API key provided. Please provide a valid API key.")

        if self.service == "vllm":
            if not self.api_url:
                raise ValueError("No API URL provided. Please provide a valid API URL.")
            self.client = OpenAI(base_url=f"{self.api_url}/v1", api_key=self.api_key)
        elif self.service == "together":
            self.client = Together(api_key=self.api_key)
        elif self.service == "openai":
            self.client = OpenAI(api_key=self.api_key)
        else:
            raise ValueError(f"Invalid service: {self.service}")

    def get_available_models(self) -> List[str]:
        """Get list of available AI models"""
        return AVAILABLE_MODELS

    def get_available_services(self) -> List[str]:
        """Get list of available services"""
        return AVAILABLE_SERVICES

    def get_structured_response_function(self) -> Any:
        """Get the structured response function"""
        if self.service == "together":
            return self.client.chat.completions.create
        return self.client.beta.chat.completions.parse

    def prompt_llm(
        self,
        prompt: str,
        response_format: Optional[Any] = None,
        return_json: bool = False,
    ) -> str | Any:
        """
        Main function to prompt an LLM via the Together API

        Args:
            prompt: The text prompt to send to the model
            response_format: The response format to use

        Returns:
            Generated text response or parsed response if response_format is provided
        """
        print(f"\nPrompting\n\nModel: {self.model}\n\nService: {self.service}\n\n")
        if not self.client:
            raise ValueError("Client not initialized. Please provide a valid API key.")

        if self.model not in AVAILABLE_MODELS:
            print(
                f"Warning: Model {self.model} not in available models list. Using default."
            )
            model = "meta-llama/Meta-Llama-3-8B-Instruct-Lite"
        else:
            model = self.model

        try:
            if response_format:
                structured_response_function = self.get_structured_response_function()
                response = structured_response_function(
                    model=model,
                    messages=[{"role": "user", "content": prompt}],
                    max_tokens=self.max_tokens,
                    temperature=self.temperature,
                    response_format=(
                        {
                            "type": "json_schema",
                            "schema": response_format.model_json_schema(),
                        }
                        if self.service == "together"
                        else response_format
                    ),
                )
                if self.service == "together":
                    output = response.choices[0].message.content
                    output = response_format.model_validate_json(output)
                else:
                    output = response.choices[0].message.parsed
            else:
                response = self.client.chat.completions.create(
                    model=model,
                    messages=[{"role": "user", "content": prompt}],
                    max_tokens=self.max_tokens,
                    temperature=self.temperature,
                )
                output = response.choices[0].message.content

            if self.with_linebreak:
                output = textwrap.fill(output, width=80)

            if return_json:
                return extract_json_from_response(output)

            return output

        except Exception as e:
            print(f"Error calling LLM: {e}")
            return f"Error: {str(e)}"

    def generate_text(self, prompt: str) -> str:
        """Generate text using specified parameters"""
        return self.prompt_llm(prompt)

    def generate_quiz_content(
        self, topic: str, difficulty: str = "intermediate", question_count: int = 5
    ) -> str:
        """Generate educational quiz content"""
        prompt = f"""Create a {difficulty} level quiz about {topic} with {question_count} questions. 
        Include multiple choice questions with explanations for each answer."""
        return self.prompt_llm(prompt)

    def analyze_content(self, text: str, analysis_type: str = "summary") -> str:
        """Analyze and process text content"""
        prompt = f"""Perform a {analysis_type} analysis of the following text:
        
        {text}
        
        Please provide a detailed {analysis_type}."""
        return self.prompt_llm(prompt)

    def provide_tutoring(
        self, subject: str, concept: str, difficulty_level: str = "beginner"
    ) -> str:
        """Provide educational tutoring and explanations"""
        prompt = f"""Act as a {difficulty_level} level tutor for {subject}. 
        Explain the concept of {concept} in a clear, educational manner with examples."""
        return self.prompt_llm(prompt)

    def process_document(
        self, document_path: str, processing_type: str = "summarize"
    ) -> str:
        """Process documents (placeholder for document processing)"""
        prompt = f"""Process the document at {document_path} and {processing_type} its content."""
        return self.prompt_llm(prompt)


# Global instance for backward compatibility
agent_manager = None


def initialize_agent_manager(
    api_key: str = None,
    model: str = "meta-llama/Meta-Llama-3-8B-Instruct-Lite",
    max_tokens: int = 1000,
    temperature: float = 0.7,
    with_linebreak: bool = False,
) -> AIAgentManager:
    """Initialize the global agent manager"""
    global agent_manager
    agent_manager = AIAgentManager(
        api_key=api_key,
        model=model,
        max_tokens=max_tokens,
        temperature=temperature,
        with_linebreak=with_linebreak,
    )
    return agent_manager


def get_agent_modules() -> List[Dict[str, Any]]:
    """Get available agent modules"""
    return AGENT_MODULES


def get_available_models() -> List[str]:
    """Get available AI models"""
    return AVAILABLE_MODELS


# Backward compatibility function
def prompt_llm(prompt: str, with_linebreak: bool = False, model: str = None) -> str:
    """
    Legacy function for backward compatibility
    This function allows us to prompt an LLM via the Together API
    """
    global agent_manager
    if not agent_manager:
        raise ValueError(
            "Agent manager not initialized. Call initialize_agent_manager() first."
        )

    return agent_manager.prompt_llm(prompt)


def main():
    """Main function to demonstrate agent capabilities"""
    parser = argparse.ArgumentParser(description="AI Agent Manager")
    parser.add_argument(
        "-k", "--api_key", type=str, default=None, help="Together AI API key"
    )
    parser.add_argument(
        "--list-modules", action="store_true", help="List available agent modules"
    )
    parser.add_argument(
        "--list-models", action="store_true", help="List available AI models"
    )
    parser.add_argument(
        "--prompt",
        type=str,
        default="Write a 3 line post about pizza",
        help="Text prompt to send to the model",
    )
    parser.add_argument(
        "--model", type=str, default=AVAILABLE_MODELS[0], help="AI model to use"
    )

    args = parser.parse_args()

    # Initialize agent manager
    manager = initialize_agent_manager(args.api_key)

    if args.list_modules:
        print("\nAvailable Agent Modules:")
        print("-" * 50)
        for module in AGENT_MODULES:
            print(f"• {module['name']}: {module['description']}")
            print(f"  Function: {module['function']}")
            print(f"  Parameters: {', '.join(module['parameters'])}")
            print()
        return

    if args.list_models:
        print("\nAvailable AI Models:")
        print("-" * 50)
        for i, model in enumerate(AVAILABLE_MODELS, 1):
            print(f"{i}. {model}")
        print()
        return

    # Example usage
    print(f"\nUsing model: {args.model}")
    print(f"Prompt: {args.prompt}")
    print("-" * 80)

    try:
        response = manager.prompt_llm(args.prompt)
        print("\nResponse:")
        print(response)
    except Exception as e:
        print(f"\nError: {e}")

    print("-" * 80)


def extract_json_from_response(response: str) -> List[Dict[str, Any]]:
    """Extract JSON from AI response text"""
    import json
    import re

    # Try to find JSON array or object (original approach)
    json_match = re.search(r"(\[.*\]|\{.*\})", response, re.DOTALL)
    if json_match:
        try:
            return json.loads(json_match.group(1))
        except json.JSONDecodeError:
            pass

    # Try parsing the entire response (original approach)
    try:
        return json.loads(response.strip())
    except json.JSONDecodeError:
        # Apply more sophisticated cleaning and extraction only after initial attempts fail
        response_cleaned = response.strip()

        # Remove common introductory phrases
        intro_patterns = [
            r"^Here is the generated.*?:\s*",
            r"^Here's the.*?:\s*",
            r"^The.*?is:\s*",
            r"^Generated.*?:\s*",
            r"^Output:\s*",
            r"^Result:\s*",
            r"^Response:\s*",
        ]

        for pattern in intro_patterns:
            response_cleaned = re.sub(
                pattern, "", response_cleaned, flags=re.IGNORECASE | re.MULTILINE
            )

        response_cleaned = response_cleaned.strip()

        # Try to find JSON array or object with cleaned response
        json_match = re.search(r"(\[.*\]|\{.*\})", response_cleaned, re.DOTALL)
        if json_match:
            json_str = json_match.group(1)
            try:
                return json.loads(json_str)
            except json.JSONDecodeError:
                # Try cleaning up common JSON issues
                json_str = re.sub(r",(\s*[\]\}])", r"\1", json_str)
                try:
                    return json.loads(json_str)
                except json.JSONDecodeError:
                    pass

        # Try parsing the entire cleaned response
        try:
            return json.loads(response_cleaned)
        except json.JSONDecodeError:
            # Last attempt: line-by-line extraction
            lines = response_cleaned.split("\n")
            json_lines = []
            bracket_count = 0
            brace_count = 0
            started = False

            for line in lines:
                stripped = line.strip()
                if not started and (
                    stripped.startswith("[") or stripped.startswith("{")
                ):
                    started = True

                if started:
                    json_lines.append(line)
                    bracket_count += line.count("[") - line.count("]")
                    brace_count += line.count("{") - line.count("}")

                    # If we've closed all brackets/braces, we're done
                    if bracket_count <= 0 and brace_count <= 0 and started:
                        break

            if json_lines:
                try:
                    json_str = "\n".join(json_lines)
                    return json.loads(json_str)
                except json.JSONDecodeError:
                    pass

            raise ValueError(
                f"Could not extract valid JSON from response\nResponse:\n{response}"
            )
