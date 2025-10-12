from drbench.agents.utils import prompt_llm


class AbstractExaminer:
    def __init__(self, model_name):
        raise NotImplementedError("Subclasses should implement this method.")

    def extract_info_from_report(self, report, question) -> str:
        raise NotImplementedError("Subclasses should implement this method.")


class GenericLLMExaminer(AbstractExaminer):
    def __init__(self, model_name):
        self.model = model_name

    def extract_info_from_report(self, report, question) -> str:
        response = prompt_llm(
            model=self.model,
            prompt=f"{report}\n\n{question}",
        )
        return response
