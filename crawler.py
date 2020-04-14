#!/usr/bin/python3
# encoding: utf-8
# Crawler
# By Guanicoe
# guanicoe@pm.me
# https://github.com/guanicoe/crawler

import time
import zmq
from multiprocessing import Process
import re
import requests
from urllib.parse import urlsplit
from collections import deque
from bs4 import BeautifulSoup
import pandas as pd
import json
from validate_email import validate_email
import hashlib
import logging
logger = logging.getLogger()
handler = logging.StreamHandler()
formatter = logging.Formatter('\n%(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)
import argparse
import os
import lxml
import sys
import signal
import shutil
import concurrent.futures as futures


""" GLOBAL """
HEADER = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 6.1) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/41.0.2228.0 Safari/537.3'}
RGX = r"""(?:[a-z0-9!#$%&'*+/=?^_`{|}~-]+(?:\.[a-z0-9!#$%&'*+/=?^_`{|}~-]+)*|"(?:[\x01-\x08\x0b\x0c\x0e-\x1f\x21\x23-\x5b\x5d-\x7f]|\\[\x01-\x09\x0b\x0c\x0e-\x7f])*")@(?:(?:[a-z0-9](?:[a-z0-9-]*[a-z0-9])?\.)+[a-z0-9](?:[a-z0-9-]*[a-z0-9])?|\[(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?|[a-z0-9-]*[a-z0-9]:(?:[\x01-\x08\x0b\x0c\x0e-\x1f\x21-\x5a\x53-\x7f]|\\[\x01-\x09\x0b\x0c\x0e-\x7f])+)\])"""
VERSION = "0.2"
EXCLUDEEXT = ['jpeg', 'jpg', 'gif', 'pdf', 'png', 'ppsx', 'f4v', 'mp3', 'mp4', 'exe', 'dmg', 'zip', 'avi', 'wmv', 'pptx', "exar1", "edx", "epub"]
EXCLUDEURL = ["whatsapp", 'youtube', "facebook", "twitter", "youtu", "69.175.83.8", "google", 'flickr', 'commailto', '.com#', "pinterest", "linkedin", "zencart", "wufoo", "youcanbook", 'instagram']
logLvel = {0: logging.CRITICAL,
               1: logging.ERROR,
               2: logging.WARNING,
               3: logging.INFO,
               4: logging.DEBUG}
""" GLOBAL """


class GeneratParameters():
    def __init__(self, args):

        #Setting log
        """if args.verbose == 4:
            tb = 1000
        else:
            tb = 0
        sys.set_coroutine_origin_tracking_depth(tb)"""
        if args.verbose > 4:
            self.verbose = 4
        elif args.verbose < 0:
            self.verbose = 0
        else:
            self.verbose = args.verbose
        #logging.basicConfig(level=logLvel[verbose])

        # Format URL
        self.urlsplit = urlsplit(args.url)
        self.url = f"{self.urlsplit.scheme}://{self.urlsplit.netloc}"
        self.domains = args.domain
        if not self.domains:
            domain = self.urlsplit.netloc.split('.')
            if len(domain) == 2:
                self.folder = domain[0]
            else:
                self.folder = domain[1]
            self.scope = False
        else:
            self.folder = self.domains[0]
            self.scope = True

        # Set constats
        self.workers = args.workers
        self.header = args.header
        # Set limit
        if args.unlimit:
            self.limit = 'Unlimited'
        else:
            self.limit = args.limit

        # set Output

        if args.output_dir is not None:
            self.folder = args.output_dir
        self.cwd = os.getcwd()
        self.listdir = os.listdir(self.cwd)
        self.outputDir = os.path.join(self.cwd, self.folder)

        if os.path.exists(self.outputDir):
            ow = 'n'
            while True:
                ow = input(f"[!] WARNING - forlder {self.folder} already exists. Overwrite? [n/Y] ?")
                if ow == "Y":
                    shutil.rmtree(self.outputDir)
                    break
                elif ow == "n":
                    exit()
        os.makedirs(self.outputDir)





def welcome():
    logo = f"""
      /$$$$$$                                   /$$
     /$$__  $$                                 | $$
    | $$  \__/  /$$$$$$  /$$$$$$  /$$  /$$  /$$| $$  /$$$$$$   /$$$$$$
    | $$       /$$__  $$|____  $$| $$ | $$ | $$| $$ /$$__  $$ /$$__  $$
    | $$      | $$  \__/ /$$$$$$$| $$ | $$ | $$| $$| $$$$$$$$| $$  \__/
    | $$    $$| $$      /$$__  $$| $$ | $$ | $$| $$| $$_____/| $$
    |  $$$$$$/| $$     |  $$$$$$$|  $$$$$/$$$$/| $$|  $$$$$$$| $$
     \______/ |__/      \_______/ \_____/\___/ |__/ \_______/|__/

                                                v{VERSION} guanicoe
    """
    print(logo)


def printParam(parameters):
    param = f"""
###########################################################################

    Base URL: {parameters.url}
    Limit scope: {parameters.scope}
    Domains : {parameters.domains}
    Number workers: {parameters.workers}
    Limit set: {parameters.limit}
    Output: {parameters.outputDir}
    Header: {parameters.header}


###########################################################################
    """

    print(param)


def timeout(timelimit):
    def decorator(func):
        def decorated(*args, **kwargs):
            with futures.ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(func, *args, **kwargs)
                try:
                    result = future.result(timelimit)
                except futures.TimeoutError:
                    logging.warning(f'[!] Timeout called on {func.__qualname__}')
                    result = kwargs.get('timeo_data')
                executor._threads.clear()
                futures.thread._threads_queues.clear()
                return result
        return decorated
    return decorator





@timeout(30)
def creatSoup(work,
              timeo_data={"state": False, "content_type": None,
                          "response": None, "oldsoup": "",
                          "error": "Timeout"}):
    typelist = ['text/html']
    url, oldsoup = work['url'], work['oldsoup']

    try:
        response = requests.get(url, headers=HEADER)
        soup = BeautifulSoup(response.text, 'lxml')
        hash = hashlib.md5(str(soup).encode()).hexdigest()
        content_type = response.headers.get('content-type')
        if hash in oldsoup:
            return {"state": False, "content_type": content_type,
                    "response": None, "oldsoup": oldsoup, "error": None}
        else:
            oldsoup.append(hash)
        if any([tps in content_type for tps in typelist]):
            output = {"state": True, "content_type": content_type,
                      "response": response, "oldsoup": oldsoup, "error": None}
        else:
            output = {"state": False, "content_type": content_type,
                      "response": None, "oldsoup": oldsoup, "error": None}
    except Exception as e:
        output = {"state": False, "content_type": None,
                  "response": None, "oldsoup": oldsoup, "error": e}

    return output


def cleanurl(url):
    parts = urlsplit(url)
    base_url = "{0.scheme}://{0.netloc}".format(parts)
    if '/' in parts.path:
        path = url[:url.rfind('/')+1]
    else:
        path = url
    return parts, base_url, path


def saveResult(dict, dir, printRes=False, save=True, getUniques=True):
    df = pd.DataFrame(dict, columns=["email", "url"])
    df_unique = df['email'].copy()
    df_unique.drop_duplicates(inplace=True)
    df_unique.reset_index(drop=True)
    try:
        df.to_csv(os.path.join(dir, "email_list.csv"), index=False)
        if save:
            df_unique.to_csv(os.path.join(dir, "emails.csv"), index=False)
    except Exception as e:
        logging.debug(f'[!] PROCESS - Could note save dfs: {e}')

    if printRes:
        logging.critical('\n[+] Result')
        if not df_unique.empty:
            logging.critical(df_unique)
        else:
            logging.critical("[+] No emails found...\n")

    if getUniques:
        return df_unique


@timeout(30)
def readhtml(response, work, timeo_data=[[], []]):

    excludeCHAR = ["/", "+", "*", "`", "%", "=", "#", "{", "}", "(", ")", "[",
                   "]", "'", "domain.com", 'email.com']
    new_emails = set(re.findall(RGX, response.text, re.I))
    falsepos = set()

    for email in new_emails:
        falsepos.update([email for e in excludeCHAR if e in email])
    new_emails -= falsepos

    soup = BeautifulSoup(response.text, 'lxml')

    if not work['domaines']:
        include = []
    else:
        include = work['domaines']

    parts, base_url, path = cleanurl(work['url'])
    links = []
    for anchor in soup.find_all("a"):
        if "href" in anchor.attrs:
            link = anchor.attrs["href"]
        else:
            link = ''
        if link.startswith('//'):
            link = link[2:]
        if link.startswith('www.'):
            link = "http://"+link
        if link.startswith('/'):
            link = base_url + link

        elif not link.startswith('http'):
            link = path + link

        if not any(ext in link for ext in EXCLUDEURL):
            if all(inc in link for inc in include):
                if link not in work['unscraped'] + work['scraped']:
                    links.append(link)
    return [links, list(new_emails)]


def signal_handler(sig, frame):
    context = zmq.Context()
    # Connect to MASTER
    masterPUSH = context.socket(zmq.PUSH)
    masterPUSH.connect("tcp://127.0.0.1:5551")

    masterPUSH.send_json(json.dumps({'name': 'key', 'state': "q"}))
    #logging.critical("[!] Keyinterrupt ctrl+c heard. Stopping")
    context.destroy(linger=0)


def MASTER(workers):
    context = zmq.Context()
    results_receiver = context.socket(zmq.PULL)
    results_receiver.bind("tcp://127.0.0.1:5551")

    socketPUB = context.socket(zmq.PUB)
    socketPUB.bind("tcp://127.0.0.1:5553")

    poller = zmq.Poller()
    poller.register(results_receiver, zmq.POLLIN)

    logging.warning("[+] MASTER is online")
    logging.debug(f"[i] MASTER - Listening for {workers} workers, producer and sink")

    count, sink, producer = 0, 0, 0

    start_time = time.time()
    while True:
        if time.time() - start_time > workers*5:
            logging.critical("[-] MASTER - Processes did not start -- TIMEOUT")
            break
        if count < workers or not sink or not producer:
            socks = dict(poller.poll())
            if socks.get(results_receiver) == zmq.POLLIN:
                recv = json.loads(results_receiver.recv_json())
                if recv == {'name': 'worker', 'state': 'start'}:
                    count += 1
                    logging.debug(f"[i] MASTER - {count}/{workers} worker connected")
                elif recv == {'name': 'sink', 'state': 'start'}:
                    logging.debug(f"[i] MASTER - sink connected")
                    sink = True
                elif recv == {'name': 'producer', 'state': 'start'}:
                    logging.debug(f"[i] MASTER - producer connected")
                    producer = True
        elif count == workers and sink and producer:
            break

    logging.critical(f"[+] MASTER - Let's go!")
    socketPUB.send_string("producer go")

    while True:
        socks = dict(poller.poll(100))
        if socks.get(results_receiver) == zmq.POLLIN:
            recv = json.loads(results_receiver.recv_json())
            if recv == {'name': 'producer', 'state': 'done'}:
                socketPUB.send_string("worker kill")
                socketPUB.send_string("sink kill")
                break
            elif recv == {'name': 'worker', 'state': 'quit'}:
                socketPUB.send_string("producer kill")
                socketPUB.send_string("worker kill")
                socketPUB.send_string("sink kill")
                break
            elif recv == {'name': 'sink', 'state': 'quit'}:
                socketPUB.send_string("producer kill")
                socketPUB.send_string("worker kill")
                break
            elif recv['name'] == 'key':
                char = recv['state']
                if char == 'q':  #
                    socketPUB.send_string("producer kill")
                    socketPUB.send_string("worker kill")
                    socketPUB.send_string("sink kill")
                else: # NOT PROGRAMMED. NEED TO FIND A WAY FOR LINUX TO LISTEN TO KEY
                    logging.info("\n [i] MASTER - Fetching results...\n")
                    socketPUB.send_string("producer print")
            else:
                logging.debug(f"""[?] MASTER - poller triggered
                                  but not understood: {recv}""")

    logging.debug('\n[i] MASTER - closing service')
    context.destroy(linger=0)


def WORKER():
    context = zmq.Context()
    # Connect to MASTER
    masterPUSH = context.socket(zmq.PUSH)
    masterPUSH.connect("tcp://127.0.0.1:5551")

    masterSUB = context.socket(zmq.SUB)
    masterSUB.connect("tcp://localhost:5553")
    masterSUB.setsockopt_string(zmq.SUBSCRIBE, "worker")
    # recieve work
    work_receiver = context.socket(zmq.PULL)
    work_receiver.connect("tcp://127.0.0.1:5557")
    # send work
    consumer_sender = context.socket(zmq.PUSH)
    consumer_sender.connect("tcp://127.0.0.1:5558")

    # Creat pollers
    poller = zmq.Poller()
    poller.register(work_receiver, zmq.POLLIN)
    poller.register(masterSUB, zmq.POLLIN)

    masterPUSH.send_json(json.dumps({"name": "worker", "state": "start"}))
    # Define variables
    data = {"state": False}

    while True:

        socks = dict(poller.poll())
        if socks.get(work_receiver) == zmq.POLLIN:
            work = json.loads(work_receiver.recv_json())
            extension = work['url'].split('.')[-1].lower()

            output = {"initUrl": work['url'], "emaildict": None,
                      "linksSet": None, "oldsoup": None,
                      "empty": True}

            if extension not in EXCLUDEEXT:
                data = creatSoup(work)
                try:
                    if data['state']:
                        linksSet, emailsSet = readhtml(data['response'], work)
                        emaildict = [{"email": email, "url": work['url']} for email in emailsSet]
                        output = {"initUrl": work['url'], "emaildict": emaildict,
                                  "linksSet": linksSet, "oldsoup": data['oldsoup'],
                                  "empty": False}
                except Exception as e:
                    print(e)

            consumer_sender.send_json(json.dumps(output))

        elif socks.get(masterSUB) == zmq.POLLIN:
            recv = masterSUB.recv_string()
            if recv.split(' ')[1] == 'kill':
                logging.debug('[i] WORKER - closing service')
                break

    context.destroy(linger=0)


def SINK():
    context = zmq.Context()
    # Connect to MASTER
    masterPUSH = context.socket(zmq.PUSH)
    masterPUSH.connect("tcp://127.0.0.1:5551")

    masterSUB = context.socket(zmq.SUB)
    masterSUB.connect("tcp://localhost:5553")
    masterSUB.setsockopt_string(zmq.SUBSCRIBE, "sink")

    # Receive from woker
    results_receiver = context.socket(zmq.PULL)
    results_receiver.bind("tcp://127.0.0.1:5558")

    # Send to producer
    report_socket = context.socket(zmq.PUSH)
    report_socket.bind("tcp://127.0.0.1:5559")

    poller = zmq.Poller()
    poller.register(results_receiver, zmq.POLLIN)
    poller.register(masterSUB, zmq.POLLIN)

    masterPUSH.send_json(json.dumps({"name": "sink", "state": "start"}))

    count = 0
    while True:
        socks = dict(poller.poll())
        if socks.get(results_receiver) == zmq.POLLIN:
            recv = json.loads(results_receiver.recv_json())
            count += 1
            recv['count'] = count
            report_socket.send_json(json.dumps(recv))
        elif socks.get(masterSUB) == zmq.POLLIN:
            recv = masterSUB.recv_string()
            if recv.split(' ')[1] == 'kill':
                logging.debug('[i] SINK - closing service')
                break

    context.destroy(linger=0)


def PRODUCER(data):
    context = zmq.Context()

    # Connect to MASTER
    masterPUSH = context.socket(zmq.PUSH)
    masterPUSH.connect("tcp://127.0.0.1:5551")

    masterSUB = context.socket(zmq.SUB)
    masterSUB.connect("tcp://localhost:5553")
    masterSUB.setsockopt_string(zmq.SUBSCRIBE, "producer")

    zmq_socket = context.socket(zmq.PUSH)
    zmq_socket.bind("tcp://127.0.0.1:5557")

    get_sink = context.socket(zmq.PULL)
    get_sink.connect("tcp://127.0.0.1:5559")
    # Start your result manager and workers before you start your producers
    poller = zmq.Poller()
    poller.register(get_sink, zmq.POLLIN)
    poller.register(masterSUB, zmq.POLLIN)

    unscraped = deque([data.url])
    scraped = set()
    emails = set()
    numberEmails = 0
    emaildict = []
    oldsoup = set()
    queue = 0
    count = 0
    work_list = deque([])
    limiteStop = True

    masterPUSH.send_json(json.dumps({"name": "producer", "state": "start"}))

    masterSUB.recv_string()

    while True:
        try:
            while len(unscraped) and limiteStop:
                if isinstance(data.limit, int):
                    if len(scraped) >= data.limit-1:
                        limiteStop = False
                url = unscraped.popleft()
                scraped.add(url)
                work = {"url": url, "oldsoup": list(oldsoup),
                        "domaines": data.domains, 'scraped': list(scraped),
                        'unscraped': list(unscraped)}
                work_list.append(work)

            socks = dict(poller.poll(100))
            if socks.get(get_sink) == zmq.POLLIN:
                sink = json.loads(get_sink.recv_json())
                queue -= 1
                count = sink['count']

                if not sink['empty']:
                    emaildict = emaildict + sink['emaildict']
                    for link in sink['linksSet']:
                        if link not in list(scraped) + list(unscraped):
                            unscraped.append(link)

                emails = saveResult(emaildict, data.outputDir, getUniques=True)
                if numberEmails < len(emails):
                    saveResult(emaildict, data.outputDir, printRes=True, save=False)
                    numberEmails = len(emails)
                sys.stdout.write(f"\r" + " " * 80)
                sys.stdout.write(f"""\r[i] PRODUCER (SCRAPED: {count}, EMAILS: {numberEmails}) - {sink['initUrl'][:60]}...""")
                #  , end='',  flush=True)

            elif len(work_list):
                while queue < 1000 and len(work_list):
                    work = work_list.popleft()
                    queue += 1
                    zmq_socket.send_json(json.dumps(work))

            elif count == len(scraped) and queue == 0:
                masterPUSH.send_json(json.dumps({"name": "producer",
                                                 "state": "done"}))
                saveResult(emaildict, data.outputDir, printRes=True)
                break

            elif socks.get(masterSUB) == zmq.POLLIN:
                recv = masterSUB.recv_string()
                if "kill" in recv:
                    logging.critical('[!] PRODUCER was killed')
                    saveResult(emaildict, data.outputDir, printRes=True, save=True)
                    break
                elif "print" in recv:
                    saveResult(emaildict, data.outputDir, printRes=True, save=False)
        except KeyboardInterrupt:
            logging.critical('[!] PRODUCER - Keyboard interrupt, stopping!')
            break

    context.destroy(linger=0)
    return



if __name__ == '__main__':

    welcome()

    parser = argparse.ArgumentParser(description='Process some integers.')
    parser.add_argument('-u', '--url', type=str,
                        required=True, help='Url to crawl')
    parser.add_argument('-d', '--domain', nargs="+", default=False,
                        help="""Domain name to keep in scope (ex: -d domain1,
                                domain2). The first domain will be used as name
                                for output. If not specified, the script will
                                go outside the webite (will take a long time
                                as it will basically scan the internet).
                                The output name will be guessed from url."""
                        )
    parser.add_argument('-w', '--workers', type=int, default=40,
                        help='Number of workers (default: 40)')
    parser.add_argument('-l', '--limit', type=int, default=5000,
                        help="""Limite the number of pages to crawl
                                (default: 5000)"""
                        )
    parser.add_argument('-ul', '--unlimit', action='store_true',
                        help="""Do not limit the number of pages to scan.
                                This will disable -l flag. (default: False)"""
                        )
    parser.add_argument('-o', '--output-dir', type=str,
                        help="""Specify which directory to save the date.
                                (default is URL)"""
                        )
    parser.add_argument('-H', '--header', type=str,
                        default=HEADER,
                        help=f"""Specify which directory to save the date.
                                (default is "{HEADER}")"""
                        )
    parser.add_argument('-v', '--verbose', action='count', default=0,
                        help="""TODO: Will define the level of verbose.
                                Sets the level of logging"""
                        )
    parser.add_argument('--version', action='version',
                        version=VERSION, help='Returns the version number')

    args = parser.parse_args()
    # print(args)







    data = GeneratParameters(args)
    logger.setLevel(logLvel[data.verbose])

    printParam(data)
    # Start WORKERS
    processes = []
    start = time.time()

    signal.signal(signal.SIGINT, signal_handler)

    """p = Process(target=KEYPRESS)
    p.daemon = True
    p.start()
    processes.append(p)"""

    p = Process(target=MASTER, args=(data.workers,),
                                name="MASTER")
    logging.debug(f'[i] Starting Master: {p.name}')
    p.daemon = True
    p.start()
    processes.append(p)

    for n in range(data.workers):
        p = Process(target=WORKER, name="WORKER")
        p.daemon = True
        p.start()
        processes.append(p)

    p = Process(target=SINK, name="SINK")
    p.daemon = True
    p.start()
    processes.append(p)


    PRODUCER(data)

    logging.warning("[i] Finalising, \t")
    for p in processes:
        p.terminate()

    logging.critical(f'[Done in {int(round(time.time() - start, 0))}s]')
