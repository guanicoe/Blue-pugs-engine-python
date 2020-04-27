#!/usr/bin/python3
# encoding: utf-8
# Crawler
# By Guanicoe
# guanicoe@pm.me
# https://github.com/guanicoe/crawler

import time
import zmq
# from multiprocessing import Process
from billiard import Process, Value
import re
import requests
from urllib.parse import urlsplit
from collections import deque
from bs4 import BeautifulSoup
import pandas as pd
import numpy as np
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
import yaml

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
def creatSoup(work, HEADER,
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
    logging.debug(f'[+] Emails cached: {len(df_unique)}')

    if getUniques:
        return df_unique


@timeout(30)
def readhtml(response, work, EXCLUDEURL, RGX, timeo_data=[[], []]):

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


def signal_handler(data, sig, frame):
    context = zmq.Context()
    # Connect to MASTER
    port = data.port
    masterPUSH = context.socket(zmq.PUSH)
    masterPUSH.connect(f"tcp://127.0.0.1:{port}")#5551")

    masterPUSH.send_json(json.dumps({'name': 'key', 'state': "q"}))
    #logging.critical("[!] Keyinterrupt ctrl+c heard. Stopping")
    context.destroy(linger=0)


def MASTER(data):
    context = zmq.Context()

    port = data.port
    workers = data.workers
    logging.debug('[i] MASTER - connecting to results_receiver')
    results_receiver = context.socket(zmq.PULL)
    results_receiver.bind(f"tcp://127.0.0.1:{port}")#5551")

    logging.debug('[i] MASTER - connecting to socketPUB')
    socketPUB = context.socket(zmq.PUB)
    socketPUB.bind(f"tcp://127.0.0.1:{port+1}")#5553")

    logging.debug('[i] MASTER - setting poller')
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
                logging.critical(f"[i] MASTER - received done message from producer")
                socketPUB.send_string("worker kill")
                socketPUB.send_string("sink kill")
                break
            elif recv == {'name': 'worker', 'state': 'quit'}:
                logging.critical(f"[i] MASTER - received quit message from worker")
                socketPUB.send_string("producer kill")
                socketPUB.send_string("worker kill")
                socketPUB.send_string("sink kill")
                break
            elif recv == {'name': 'sink', 'state': 'quit'}:
                logging.critical(f"[i] MASTER - received quit message from sink")
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


def WORKER(data, HEADER, EXCLUDEEXT, EXCLUDEURL, RGX):
    context = zmq.Context()
    # Connect to MASTER

    port = data.port
    masterPUSH = context.socket(zmq.PUSH)
    masterPUSH.connect(f"tcp://127.0.0.1:{port}")#5551")

    masterSUB = context.socket(zmq.SUB)
    masterSUB.connect(f"tcp://127.0.0.1:{port+1}")#5553")
    masterSUB.setsockopt_string(zmq.SUBSCRIBE, "worker")
    # recieve work
    work_receiver = context.socket(zmq.PULL)
    work_receiver.connect(f"tcp://127.0.0.1:{port+2}")#5557")
    # send work
    consumer_sender = context.socket(zmq.PUSH)
    consumer_sender.connect(f"tcp://127.0.0.1:{port+4}")#:5558")

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
                data = creatSoup(work, HEADER)
                try:
                    if data['state']:
                        linksSet, emailsSet = readhtml(data['response'], work, EXCLUDEURL, RGX)
                        emaildict = [{"email": email, "url": work['url']} for email in emailsSet]
                        output = {"initUrl": work['url'], "emaildict": emaildict,
                                  "linksSet": linksSet, "oldsoup": data['oldsoup'],
                                  "empty": False}
                except Exception as e:
                    logging.debug(f'[i] WORKER - exception hit {e}')

            consumer_sender.send_json(json.dumps(output))

        elif socks.get(masterSUB) == zmq.POLLIN:
            recv = masterSUB.recv_string()
            if recv.split(' ')[1] == 'kill':
                logging.debug('[i] WORKER - closing service')
                break

    context.destroy(linger=0)


def SINK(data):
    context = zmq.Context()

    port = data.port
    # Connect to MASTER
    logging.debug('[i] SINK - connecting to masterPUSH')
    masterPUSH = context.socket(zmq.PUSH)
    masterPUSH.connect(f"tcp://127.0.0.1:{port}")#5551")

    logging.debug('[i] SINK - connecting to masterSUB')
    masterSUB = context.socket(zmq.SUB)
    masterSUB.connect(f"tcp://127.0.0.1:{port+1}")#5553")
    masterSUB.setsockopt_string(zmq.SUBSCRIBE, "sink")

    # Receive from woker
    logging.debug('[i] SINK - connecting to results_receiver')
    results_receiver = context.socket(zmq.PULL)
    results_receiver.bind(f"tcp://127.0.0.1:{port+4}")#:5558")

    # Send to producer
    logging.debug('[i] SINK - connecting to report_socket')
    report_socket = context.socket(zmq.PUSH)
    report_socket.bind(f"tcp://127.0.0.1:{port+3}")#5559")

    logging.debug('[i] SINK - setting poller')
    poller = zmq.Poller()
    poller.register(results_receiver, zmq.POLLIN)
    poller.register(masterSUB, zmq.POLLIN)

    logging.debug('[i] SINK - sending ready message')
    masterPUSH.send_json(json.dumps({"name": "sink", "state": "start"}))

    logging.debug('[i] SINK - starting main loop')
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
                context.destroy(linger=0)
                logging.debug('[i] SINK - closing service')
                break


def PRODUCER(data):
    context = zmq.Context()

    port = data.port

    # Connect to MASTER
    logging.debug('[i] PRODUCER - connecting to masterPUSH')
    masterPUSH = context.socket(zmq.PUSH)
    masterPUSH.connect(f"tcp://127.0.0.1:{port}")#5551")

    logging.debug('[i] PRODUCER - connecting to masterSUB')
    masterSUB = context.socket(zmq.SUB)
    masterSUB.connect(f"tcp://127.0.0.1:{port+1}")#5553")
    masterSUB.setsockopt_string(zmq.SUBSCRIBE, "producer")

    logging.debug('[i] PRODUCER - connecting to zmq_socket')
    zmq_socket = context.socket(zmq.PUSH)
    zmq_socket.bind(f"tcp://127.0.0.1:{port+2}")#5557")

    logging.debug('[i] PRODUCER - connecting to get_sink')
    get_sink = context.socket(zmq.PULL)
    get_sink.connect(f"tcp://127.0.0.1:{port+3}")#5559")
    # Start your result manager and workers before you start your producers
    logging.debug('[i] PRODUCER - setting poller')
    poller = zmq.Poller()
    poller.register(get_sink, zmq.POLLIN)
    poller.register(masterSUB, zmq.POLLIN)

    logging.debug('[i] PRODUCER - setting initial variables')
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

    logging.debug('[i] PRODUCER - sending ready message to MASTER')
    masterPUSH.send_json(json.dumps({"name": "producer", "state": "start"}))

    logging.debug('[i] PRODUCER - waiting green light from MASTER')
    masterSUB.recv_string()

    logging.debug('[i] PRODUCER - starting main loop')
    n=0
    while True:
        try:
            logging.debug(f'[{n}] PRODUCER - creating work list')
            logging.debug(f'[+] URL scraped: {len(scraped)}')
            while len(unscraped) and limiteStop:
                if len(scraped) >= data.limit-1:
                    limiteStop = False
                url = unscraped.popleft()
                scraped.add(url)
                work = {"url": url, "oldsoup": list(oldsoup),
                        "domaines": data.domains, 'scraped': list(scraped),
                        'unscraped': list(unscraped)}
                work_list.append(work)
            logging.debug(f'[{n}] PRODUCER - {work_list}')
            logging.debug(f'[{n}] PRODUCER - listening to poller')
            socks = dict(poller.poll(100))
            if socks.get(get_sink) == zmq.POLLIN:
                logging.debug(f'[{n}] PRODUCER - get_sink')
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

            elif len(work_list):
                logging.debug(f'[{n}] PRODUCER - creat queue')
                while queue < 100 and len(work_list):
                    work = work_list.popleft()
                    queue += 1
                    zmq_socket.send_json(json.dumps(work))

            elif count == len(scraped) and queue == 0:
                logging.debug(f'[{n}] PRODUCER - saving results and quitting')
                masterPUSH.send_json(json.dumps({"name": "producer",
                                                 "state": "done"}))
                saveResult(emaildict, data.outputDir, printRes=True)
                break

            elif socks.get(masterSUB) == zmq.POLLIN:
                recv = masterSUB.recv_string()
                if "kill" in recv:
                    logging.critical(f'[{n}] PRODUCER was killed')
                    saveResult(emaildict, data.outputDir, printRes=True, save=True)
                    break
        except Exception as e:
            logging.critical(f'[{n}] PRODUCER - Big error: {e}')
            break
        n+= 1
    saveResult(emaildict, data.outputDir, printRes=True)
    context.destroy(linger=0)
    return emaildict



class setParam():
    def __init__(self, param, config):
        self.verbose = int(np.clip(config['VERBOSE'], 0, 5) * 10)
        # Format URL
        self.urlsplit = urlsplit(param['url'])
        self.url = f"{self.urlsplit.scheme}://{self.urlsplit.netloc}"
        self.domains = param['domain']
        self.folder = param['reference'].replace("-", "_")

        # Set constats
        self.workers = param['workers']
        self.header = config['HEADER']
        # Set limit
        self.limit = param['limit']
        self.port = 5000 + param['port']

        # set Output
        self.cwd = os.getcwd()
        self.listdir = os.listdir(self.cwd)
        self.outputDir = os.path.join(self.cwd, 'cache', self.folder)
        if not os.path.exists(self.outputDir):
            os.makedirs(self.outputDir)


def getConfig(filename="config.yaml"):
    cwd = os.getcwd()
    configFile = os.path.join(cwd, "engine", "config.yaml")
    with open(configFile, 'r') as stream:
        try:
            config = yaml.safe_load(stream)
        except yaml.YAMLError as exc:
            logging.debug(f'[i] getConfig - error opening config file {exc}')
    return config

def crawl(param):

    config = getConfig()
    data = setParam(param=param, config= config)
    logger.setLevel(data.verbose)

    processes = []

    p = Process(target=MASTER, args=(data,), name="MASTER")
    p.start()
    processes.append(p)
    logging.info('[i] MASTER started')

    for n in range(data.workers):
        p = Process(target=WORKER, args=(data, config['HEADER'], config['EXCLUDEEXT'].split(','), config['EXCLUDEURL'].split(','), config['RGX']), name="WORKER")
        p.start()
        processes.append(p)
        logging.info(f'[i] WORKER {n}/{data.workers} started')

    p = Process(target=SINK, args=(data,), name="SINK")
    p.start()
    processes.append(p)

    logging.info(f'[i] Starting PRODUCER')
    emails = PRODUCER(data)

    logging.critical("[i] Finalising, \t")
    for p in processes:
        p.terminate()
    logging.critical('[i] Done')
    return emails


if __name__ == '__main__':
    param = {
                "url": "https://www.optovue.com/",
                "domain": ['optovue'],
                "reference": "7bf8b99a-7112-45ce-aecb-e73ebe18af13",
                "workers": 20,
                "limit": 5000,
            }
    emails = crawl(param)
    print(emails)
