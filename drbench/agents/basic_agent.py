import os

from drbench.metrics.utils.source_reader import SourceReader


class BasicAgent:
    """
    Basic agent that uses a LLM to generate a report.
    """

    def __init__(self):
        pass

    def generate_report(self, query: str, local_files):
        report = ""
        insights = []

        source_reader = SourceReader()
        for file in local_files:
            assert os.path.exists(file), f"File {file} does not exist"
            filename, content = source_reader.parse_file(file)
            report += f"Title: {filename}\nContent: {content}\n\n"

            # break into chunks of 250 words each
            chunks = break_into_chunks(content, 250)
            for chunk in chunks:
                insights.append({"claim": chunk, "citations": [os.path.basename(file)]})

        report_dict = {
            "report_text": report,
            "report_insights": insights,
        }
        return report_dict


def break_into_chunks(content, chunk_size):
    words = content.split()
    chunks = []
    for i in range(0, len(words), chunk_size):
        chunks.append(" ".join(words[i : i + chunk_size]))
    return chunks
