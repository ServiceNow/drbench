# suppress warnings
import warnings

warnings.filterwarnings("ignore")


from drbench import drbench_enterprise_space, task_loader
from drbench.agents.drbench_agent.drbench_agent import DrBenchAgent
from drbench.score_report import score_report

if __name__ == "__main__":
    # (1) Load one task
    # ----------------------
    task = task_loader.get_task_from_id(task_id="DR0001")
    print(task.summary())

    # (2) Start DRBench Enterprise Search Environment
    # ----------------------
    env = drbench_enterprise_space.DrBenchEnterpriseSearchSpace(
        task=task.get_path(),
        start_container=True,
        # auto_ports = True,  # Uncomment to use random ports
    )

    # (3) Generate Report with Your Own Agent
    # ----------------------
    dr_agent = DrBenchAgent(model="gpt-4o-mini", max_iterations=5)

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
    )
    print("Insights Recall: ", score_dict["insights_recall"])
    print("Factuality: ", score_dict["factuality"])

    # (5) Exit
    # ----------------------
    env.delete()
