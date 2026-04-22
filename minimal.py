# suppress warnings
import warnings

warnings.filterwarnings("ignore")

import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# Disable logging for specific libraries
logging.getLogger("openai").setLevel(logging.WARNING)
logging.getLogger("httpx").setLevel(logging.WARNING)

from drbench import config as drbench_config
from drbench import drbench_enterprise_space, task_loader
from drbench.agents.drbench_agent.drbench_agent import DrBenchAgent
from drbench.score_report import score_report


def _resolve_task_image(task_id: str) -> str | None:
    """Return the full per-task Docker image name if available locally or in a registry."""
    import docker

    registry = drbench_config.DRBENCH_DOCKER_REGISTRY
    prefix = drbench_config.DRBENCH_DOCKER_IMAGE
    tag = f"{prefix}:{task_id}"
    full = f"{registry}/{tag}" if registry else tag

    client = docker.from_env()
    try:
        client.images.get(full)
        return full
    except docker.errors.ImageNotFound:
        pass
    if registry:
        try:
            logging.info(f"Pulling {full} from registry...")
            client.images.pull(full)
            return full
        except Exception:
            pass
    return None


if __name__ == "__main__":
    # Configure models
    agent_model = "openrouter/openai/gpt-4o-mini"
    embedding_model = "openrouter/openai/text-embedding-ada-002"
    evaluation_model = "openrouter/openai/gpt-4o"

    # (1) Load one task
    # ----------------------
    task = task_loader.get_task_from_id(task_id="DR0001")
    print(task.summary())

    # (2) Start DRBench Enterprise Search Environment
    # If DRBENCH_DOCKER_REGISTRY is set and a per-task image exists, uses it
    # for fast startup (~8s). Otherwise uses the base image (~45s).
    # ----------------------
    task_image = _resolve_task_image("DR0001")
    if task_image:
        logging.info(f"Using pre-baked image: {task_image}")

    env = drbench_enterprise_space.DrBenchEnterpriseSearchSpace(
        task=task.get_path(),
        config={"image": task_image} if task_image else {},
        auto_ports=True,
        start_container=True,
        task_data_preloaded=bool(task_image),
    )

    # (3) Generate Report with Your Own Agent
    # ----------------------
    dr_agent = DrBenchAgent(
        model=agent_model,
        max_iterations=5,
        embedding_model=embedding_model,
    )

    report = dr_agent.generate_report(
        query=task.get_task_config()["dr_question"],
        env=env,
    )

    # (4) Evaluate Report
    # ----------------------
    score_dict = score_report(
        predicted_report=report,
        task=task,
        metrics=["insights_recall", "factuality"],
        savedir="results/minimal",
        model=evaluation_model,
        embedding_model=embedding_model,
    )
    print("Insights Recall: ", score_dict["insights_recall"])
    print("Factuality: ", score_dict["factuality"])

    # (5) Exit
    # ----------------------
    env.delete()
