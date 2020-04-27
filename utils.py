import concurrent.futures as futures
from urllib.parse import urlsplit
import pandas as pd
import logging


# DEBUG: Detailed information, typically of interest only when diagnosing problems.

# INFO: Confirmation that things are working as expected.

# WARNING: An indication that something unexpected happened, or indicative of some problem in the near future (e.g. ‘disk space low’). The software is still working as expected.

# ERROR: Due to a more serious problem, the software has not been able to perform some function.

# CRITICAL: A serious error, indicating that the program itself may be unable to continue running.


logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

formatter = logging.Formatter('%(levelname)s:%(name)s:%(message)s')

file_handler = logging.FileHandler('logs/utils.log')
file_handler.setLevel(logging.WARNING)
file_handler.setFormatter(formatter)

logger.addHandler(file_handler)


def timeout(timelimit):
    def decorator(func):
        def decorated(*args, **kwargs):
            with futures.ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(func, *args, **kwargs)
                try:
                    result = future.result(timelimit)
                except futures.TimeoutError:
                    logger.error(f'Timeout called on {func.__qualname__}')
                    result = kwargs.get('timeo_data')
                executor._threads.clear()
                futures.thread._threads_queues.clear()
                return result
        return decorated
    return decorator


def cleanurl(url):
    parts = urlsplit(url)
    base_url = "{0.scheme}://{0.netloc}".format(parts)
    if '/' in parts.path:
        path = url[:url.rfind('/')+1]
    else:
        path = url
    return parts, base_url, path


def saveResult(dict, dir):
    df = pd.DataFrame(dict, columns=["email", "url"])
    try:
        df.to_csv(os.path.join(dir, "email_list.csv"), index=False)
        logger.debug(f'Emails cached: {len(df)}')
    except Exception as e:
        logger.error(f'Could note save dfs: {e}')






# def getConfig(filename="config.yaml"):
#     cwd = os.getcwd()
#     configFile = os.path.join(cwd, "config.yaml")
#     with open(configFile, 'r') as stream:
#         try:
#             config = yaml.safe_load(stream)
#         except yaml.YAMLError as exc:
#             logging.debug(f'[i] getConfig - error opening config file {exc}')
#     return config
