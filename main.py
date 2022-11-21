import logging
import os
from app_insights import *
from internet_metrics import *

# Setup a verbose logger for the top level function, so we can track this function
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("InternetCheck")


def main():

    key = os.getenv('APPLICATIONINSIGHTS_CONNECTION_STRING')

    tracer = register_azure_exporter_with_tracer(key)

    results_speed, results_setup = run_test(tracer)
    results_combined = Merge(results_speed.dict(), results_setup)
    logger.debug("results combined: %s", results_combined)

    push_azure_speedtest_metrics(results_combined, key)


if  __name__ == "__main__":
    main()
