import logging

from drbench_utils.mattermost import MattermostUserManager

logger = logging.getLogger("mattermost data init")


if __name__ == "__main__":
    import json
    import sys
    import time
    import urllib.request

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
    logger.info("Mattermost data initialization script started.")

    args = sys.argv[1:]
    if len(args) != 1:
        logger.info("Usage: init_mattermost_data.py <path_to_users_data>")
        exit(1)

    users_data = args[0]

    logger.info("Making sure Mattermost server is ready...")
    max_retries = 30
    retries = 0

    while retries < max_retries:
        try:
            response = urllib.request.urlopen("http://localhost:8065/api/v4/system/ping")
            if response.getcode() == 200:
                ping_data = json.loads(response.read().decode("utf-8"))
                if ping_data.get("status") == "OK":
                    logger.info("Mattermost server is ready!")
                    break
        except Exception as e:
            logger.info(f"Waiting for Mattermost to be available: {e}")

        retries += 1
        logger.info(f"Retry {retries}/{max_retries}...")
        time.sleep(5)

    if retries >= max_retries:
        logger.info("Failed to connect to Mattermost after maximum retries")
        exit(1)

    # Proceed with creating users
    try:
        manager = MattermostUserManager()
        success = manager.create_all_users(users_data_path=users_data)
        if success:
            logger.info("Successfully created all users and channels!")
        else:
            logger.error("Failed to create all users and channels")
            exit(1)
    except Exception as e:
        logger.error(f"Error creating users: {e}")
        import traceback

        traceback.print_exc()
        exit(1)
