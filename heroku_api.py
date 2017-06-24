import heroku
import argparse
import os
import requests
from requests.packages.urllib3.exceptions import InsecureRequestWarning, SNIMissingWarning, InsecurePlatformWarning

from app import logger

requests.packages.urllib3.disable_warnings(InsecureRequestWarning)
requests.packages.urllib3.disable_warnings(SNIMissingWarning)
requests.packages.urllib3.disable_warnings(InsecurePlatformWarning)

# to see all environment vavialbles: heroku run printenv
# to get my process: os.getenv("DYNO")

def run(app_name, command, process_name_start_to_restart=None):
    cloud = heroku.from_key(os.getenv("HEROKU_API_KEY"))
    app = cloud.apps[app_name]
    if command=="memory":
        # need o have done this for it to work: heroku labs:enable log-runtime-metrics
        for process in app.processes:
            process_name = process.process
            logger.info(process_name)
            for line in app.logs(num=100000, ps=process_name).split("\n"):
                try:
                    if u"Error R14 (Memory quota exceeded)" in line or u"Error R15 (Memory quota vastly exceeded)" in line:
                        logger.info(line)
                except Exception:
                    pass

    if command=="restart":
        print(u"restarting {app_name}, processes that start with {process_name}".format(
            app_name=app_name, process_name=process_name_start_to_restart))
        for process in app.processes:
            process_name = process.process
            process_name_start = process_name.split(".")[0]
            if process_name_start==process_name_start_to_restart or not process_name_start_to_restart:
                process.restart()
                print(u"upon request in heroku_api, restarted {process_name}".format(
                    process_name=process_name))

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run stuff")
    parser.add_argument('--app', default=None, type=str, help="oadoi")
    parser.add_argument('--process', default=None, type=str, help="process")
    parser.add_argument('--command', default=None, type=str, help="restart")
    args = vars(parser.parse_args())
    logger.info(args)
    logger.info(u"heroku_api.py starting.")
    run(args["app"], args["command"], args["process"])
