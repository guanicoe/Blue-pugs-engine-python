#!/usr/bin/python3
# encoding: utf-8
# BluePugs Engine
# By Guanicoe
# guanicoe@pm.me
# https://github.com/guanicoe/Blue-pugs-engine
from collections import deque
from urllib.parse import urlsplit
from billiard import Process, Value
from bs4 import BeautifulSoup
import concurrent.futures as futures
import pandas as pd
import requests
import hashlib
import argparse
import lxml
import zmq
import json
import time
import os
import re
import uuid
import signal
#Custom modules
if __name__ == "__main__":
    import config
    logpath = 'bluePugs.log'
else:
    import bluepugs.engine.config as config
    logpath = os.path.join(config.LOG_DIRECTORY, 'bluePugs.log')
import logging

# DEBUG: Detailed information, typically of interest only when diagnosing problems.

# INFO: Confirmation that things are working as expected.

# WARNING: An indication that something unexpected happened, or indicative of some problem in the near future (e.g. ‘disk space low’). The software is still working as expected.

# ERROR: Due to a more serious problem, the software has not been able to perform some function.

# CRITICAL: A serious error, indicating that the program itself may be unable to continue running.

logLevel = {"DEBUG": logging.DEBUG,
            "INFO": logging.INFO,
            "WARNING": logging.WARNING,
            "ERROR": logging.ERROR,
            "CRITICAL": logging.CRITICAL}

logger = logging.getLogger(__name__)
logger.setLevel(logLevel[config.LOG_LEVEL])

formatter = logging.Formatter('%(asctime)s - %(levelname)s:%(module)s:%(name)s:%(funcName)s --- %(message)s --- [%(lineno)d]')

file_handler = logging.FileHandler(logpath)
file_handler.setLevel(logging.INFO)
file_handler.setFormatter(formatter)


stream_handler = logging.StreamHandler()
stream_handler.setLevel(logging.DEBUG)
stream_handler.setFormatter(formatter)

logger.addHandler(file_handler)
logger.addHandler(stream_handler)

global KILLING




class SetupZMQ():


    def connectZMQ(self,):
        self.context = zmq.Context()
        self.health = True

        self.masterPUSH = self.context.socket(zmq.PUSH)
        self.masterPUSH.connect(f"tcp://127.0.0.1:{self.port}")#5551")
        logger.debug(f"Successful connection to masterPUSH on port {self.port} - {self.masterPUSH}")

        self.masterSUB = self.context.socket(zmq.SUB)
        self.masterSUB.connect(f"tcp://127.0.0.1:{self.port+1}")#5553")
        self.masterSUB.setsockopt_string(zmq.SUBSCRIBE, self.who)
        logger.debug(f"Successful connection to masterSUB on port {self.port+1} - {self.masterSUB}")

    def zmqProducer(self):

        self.zmq_socket = self.context.socket(zmq.PUSH)
        self.zmq_socket.bind(f"tcp://127.0.0.1:{self.port+2}")#5557")
        logger.debug(f"Successful connection to zmq_socket on port {self.port+2} - {self.zmq_socket}")

        self.get_sink = self.context.socket(zmq.PULL)
        self.get_sink.connect(f"tcp://127.0.0.1:{self.port+3}")#5559")
        logger.debug(f"Successful connection to get_sink on port {self.port+3} - {self.get_sink}")

        return [self.zmq_socket, self.get_sink]

    def zmqWorker(self):
        # recieve work
        self.work_receiver = self.context.socket(zmq.PULL)
        self.work_receiver.connect(f"tcp://127.0.0.1:{self.port+2}")#5557")
        logger.debug(f"Successful connection to work_receiver on port {self.port+2} - {self.work_receiver}")

        self.consumer_sender = self.context.socket(zmq.PUSH)
        self.consumer_sender.connect(f"tcp://127.0.0.1:{self.port+4}")#:5558")
        logger.debug(f"Successful connection to consumer_sender on port {self.port+4} - {self.consumer_sender}")

        return [self.work_receiver, self.consumer_sender]

    def zmqSink(self):
        self.results_receiver = self.context.socket(zmq.PULL)
        self.results_receiver.bind(f"tcp://127.0.0.1:{self.port+4}")#:5558")
        logger.debug(f"Successful connection to results_receiver on port {self.port+4} - {self.results_receiver}")

        self.report_socket = self.context.socket(zmq.PUSH)
        self.report_socket.bind(f"tcp://127.0.0.1:{self.port+3}")#5559")
        logger.debug(f"Successful connection to report_socket on port {self.port+3} - {self.report_socket}")

        return [self.results_receiver, self.report_socket]

    def zmqMaster(self):

        self.masterPULL = self.context.socket(zmq.PULL)
        self.masterPULL.bind(f"tcp://127.0.0.1:{self.port}")#5551")
        logger.debug(f"Successful connection to masterPULL on port {self.port} - {self.masterPULL}")

        self.socketPUB = self.context.socket(zmq.PUB)
        self.socketPUB.bind(f"tcp://127.0.0.1:{self.port+1}")#5553")
        logger.debug(f"Successful connection to socketPUB on port {self.port+1} - {self.socketPUB}")

        return [self.masterPULL]

    def generatPoller(self, sockets):
        self.poller = zmq.Poller()
        for socket in sockets:
            self.poller.register(socket, zmq.POLLIN)
            logger.debug(f"Register {socket} OK")

    def sendToMaster(self, what):
        message = {"name": self.who, "state": what}
        self.masterPUSH.send_json(json.dumps(message))
        logger.info(f"Sent message: {message}")

    def gracefullyKill(self, tellMaster = True):
        if tellMaster:
            self.sendToMaster("quit")
        logger.warning(f"Killing process: {self.who}")
        # self.masterPUSH.close()
        # self.masterSUB.close()
        # self.work_receiver.close()
        # self.consumer_sender.close()
        # self.context.term()
        self.context.destroy(linger=0)
        logger.warning(f"Process: {self.who} killed!")

    def interpretMaster(self):
        recv = self.masterSUB.recv_string()
        if recv.split(' ')[1] == 'kill':
            logger.warning('Closing service, received kill signal from masterSUB')
            self.health = False
        else:
            logger.error(f'Received unknown message from masterSUB: {recv}')

    def countFails(self):
        self.fails += 1
        logger.warning(f"The {self.who}'s poller socket has timedout {self.fails} time(s) in a row.")
        if self.fails >= 5:
            logger.critical(f"The {self.who}'s poller socket has timedout {self.fails} times in a row and is being killed.")
            self.health = False

class KillSwitch(SetupZMQ):
    def __init__(self, data):
        self.who = "ks"
        self.port = data.port
        try:
            self.connectZMQ()
        except Exception as e:
            logger.exception(f"Failed to initialise ZMQ: {e}.")
            self.health = False
            self.gracefullyKill()

    def __call__(self):
        print("SENDING KILL SIGNAL")
        self.gracefullyKill()

class Workers(SetupZMQ):
    def __init__(self, data):

        self.data = {"state": False}

        self.fails = 0
        self.who = "worker"
        self.port = data.port

        try:
            self.connectZMQ()
            self.generatPoller(self.zmqWorker())
        except Exception as e:
            logger.exception(f"Failed to initialise ZMQ: {e}.")
            self.health = False
            self.gracefullyKill()

        if self.health:
            self.sendToMaster("start")
            self.mainLoop()
        else:
            self.gracefullyKill()


    def timeout(timelimit):
        def decorator(func):
            def decorated(*args, **kwargs):
                with futures.ThreadPoolExecutor(max_workers=1) as executor:
                    future = executor.submit(func, *args, **kwargs)
                    try:
                        result = future.result(timelimit)
                    except futures.TimeoutError:
                        logger.error(f'Timeout called on {func.__qualname__}')
                        result = kwargs.get('timeout_data')
                    executor._threads.clear()
                    futures.thread._threads_queues.clear()
                    return result
            return decorated
        return decorator



    @timeout(30)
    def creatSoup(self, work, timeout_data={ "state": False,
                                    "content_type": None,
                                    "response": None,
                                    "oldsoup": "",
                                    "error": "Timeout"}):
        typelist = ['text/html']
        url, oldsoup = work['url'], work['oldsoup']

        try:
            response = requests.get(url, headers=config.HEADER)
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
                      "response": None, "oldsoup": oldsoup, "error": str(e)}
            logger.warning(f"Exception hit on url: {url} - error reads: {e}")
        return output

    def cleanurl(self, url):
        parts = urlsplit(url)
        base_url = "{0.scheme}://{0.netloc}/".format(parts)
        if '/' in parts.path:
            path = url[:url.rfind('/')+1]
        else:
            path = url
        return parts, base_url, path

    @timeout(30)
    def readhtml(self, response, work, timeout_data=[[], []]):

        excludeCHAR = ["/", "+", "*", "`", "%", "=", "#", "{", "}", "(", ")", "[",
                       "]", "'", "domain.com", 'email.com']
        new_emails = set(re.findall(config.RGX, response.text, re.I))
        falsepos = set()
        for email in new_emails:
            falsepos.update([email for e in excludeCHAR if e in email])
        new_emails -= falsepos

        soup = BeautifulSoup(response.text, 'lxml')

        if not work['domaines']:
            include = []
        else:
            include = work['domaines']

        parts, base_url, path = self.cleanurl(work['url'])
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
            else:
                link = base_url + "/" + link

            if not link.startswith('http'):
                link = path + link

            if not any(ext in link for ext in config.BLACKLIST['URLS']):
                if any(inc in link for inc in include):
                    if link not in work['unscraped'] + work['scraped']:
                        links.append(link)

        return [links, list(new_emails)]

    def mainLoop(self):
        while self.health:

            socks = dict(self.poller.poll(config.TIMEOUT_CONSTANT))
            if socks.get(self.work_receiver) == zmq.POLLIN:
                work = json.loads(self.work_receiver.recv_json())
                output = {
                            "initUrl": work['url'],
                            "emaildict": None,
                            "linksSet": None,
                            "oldsoup": None,
                            "empty": True,
                            "error": False,
                        }
                try:
                    extension = work['url'].split('.')[-1].lower()
                    if extension not in config.BLACKLIST['EXTENSIONS'] :
                        data = self.creatSoup(work)
                        if data is None:
                            output['error'] = "data is none, error in creatSoup"
                        elif data['state']:
                            linksSet, emailsSet = self.readhtml(data['response'], work)
                            output = {
                                        "initUrl": work['url'],
                                        "emaildict": [{"email": email, "url": work['url']} for email in emailsSet],
                                        "linksSet": linksSet,
                                        "oldsoup": data['oldsoup'],
                                        "empty": False,
                                        "error": False,
                                    }
                        else:
                            output['error'] = data['error']
                except Exception as e:
                     output['error'] = True
                     logger.exception(f'Exception hit when undertaking job {e}. Work: {data}')
                self.consumer_sender.send_json(json.dumps(output))

            elif socks.get(self.masterSUB) == zmq.POLLIN:
                self.interpretMaster()

            else:
                self.countFails()

        self.gracefullyKill()

class Sink(SetupZMQ):

    """
        PARAM :: data - this is a dictionary that has the key <port> for starting the sink.

        The Sink class generates a listener to listen for workers, collect their data and
        send them back to the producer. We first initialise a few constants. We then extract
        the port from the argument <data>. We use the class we inherit from to connect to
        the different zmq sockets and generate the poller object. If all this is successful,
        we send a "start" message to MASTER and start main loop, otherwise we kill the sink

        The main loop is simple. Whilst <health> is true, we listen on the socket. This is none
        blocking. We add a large timeout of 1 minute (60e3ms) so allow for fails in case nothing
        comes. We allow for 5 fails before breaking setting <self.health> to false hence killing the sink.

        If we get a message from <results_receiver>, we take this message, add 1 to our success counter
        and send the message at the PRODUCER.
        If we get a message from <masterSUB>, we run the interpretMASTER function that only listens
        for a kill signal, which sets <self.health> to true if received, otherwise we log the unknown
        message.

    """

    def __init__(self, data):
        self.count = 0

        self.fails = 0
        self.who = "sink"
        self.port = data.port

        try:
            self.connectZMQ()
            self.generatPoller(self.zmqSink())
        except Exception as e:
            logger.exception(f"Failed to initialise ZMQ: {e}.")
            self.health = False
            self.gracefullyKill()

        if self.health:
            self.sendToMaster("start")
            self.mainLoop()
        else:
            self.gracefullyKill()

    def mainLoop(self):
        while self.health:
            socks = dict(self.poller.poll(config.TIMEOUT_CONSTANT))
            if socks.get(self.results_receiver) == zmq.POLLIN:
                recv = json.loads(self.results_receiver.recv_json())
                self.count += 1
                recv['count'] = self.count
                self.report_socket.send_json(json.dumps(recv))
            elif socks.get(self.masterSUB) == zmq.POLLIN:
                self.interpretMaster()

            else:
                self.countFails()


        self.gracefullyKill()

class Master(SetupZMQ):
    def __init__(self, data):
        self.count, self.sink, self.producer = 0, 0, 0

        self.fails = 0
        self.who = "master"
        self.port = data.port

        self.workers = data.workers


        try:
            self.connectZMQ()
            self.generatPoller(self.zmqMaster())
        except Exception as e:
            logger.exception(f"Failed to initialise ZMQ: {e}.")
            self.health = False

        if self.health:
            self.startLoop()
            self.mainLoop()
        else:
            self.gracefullyKill(tellMaster = False)

    def pubKillSockets(self, destinations):
        for who in destinations:
            self.socketPUB.send_string(f"{who} kill")

    def startLoop(self):
        start_time = time.time()
        logger.debug(f"Listening for {self.workers} workers, producer and sink. Timeout set to {self.workers*3}s")
        while True:
            if time.time() - start_time > self.workers*5:
                logger.critical("Processes did not start -- TIMEOUT")
                self.health = False
                self.pubKillSockets(['producer', 'worker', 'sink'])
                break
            if self.count < self.workers or not self.sink or not self.producer:
                socks = dict(self.poller.poll(1000))
                if socks.get(self.masterPULL) == zmq.POLLIN:
                    recv = json.loads(self.masterPULL.recv_json())
                    if recv == {'name': 'worker', 'state': 'start'}:
                        self.count += 1
                        logger.info(f"{self.count}/{self.workers} worker connected")
                    elif recv == {'name': 'sink', 'state': 'start'}:
                        logger.info(f"Sink connected")
                        self.sink = True
                    elif recv == {'name': 'producer', 'state': 'start'}:
                        logger.info(f"Producer connected")
                        self.producer = True
            elif self.count == self.workers and self.sink and self.producer:
                logger.info(f"[+] MASTER - Let's go!")
                break


    def mainLoop(self):
        self.socketPUB.send_string("producer go")
        while self.health:
            socks = dict(self.poller.poll(1000))
            if socks.get(self.masterPULL) == zmq.POLLIN:
                recv = json.loads(self.masterPULL.recv_json())
                if recv == {'name': 'producer', 'state': 'quit'}:
                    logger.warning(f"[i] MASTER - received quit message from {recv['name']}")
                    self.pubKillSockets(['worker', 'sink'])
                    break
                elif recv == {'name': 'worker', 'state': 'quit'}:
                    logger.warning(f"[i] MASTER - received quit message from {recv['name']}")
                    self.pubKillSockets(['producer', 'worker', 'sink'])
                    break
                elif recv == {'name': 'sink', 'state': 'quit'}:
                    logger.warning(f"[i] MASTER - received quit message from {recv['name']}")
                    self.pubKillSockets(['producer', 'worker'])
                    break
                elif recv == {'name': 'ks', 'state': 'quit'}:
                    logger.warning(f"[i] MASTER - received quit message from {recv['name']}")
                    self.pubKillSockets(['producer', 'worker', 'sink'])
                    break
                else:
                    logger.error(f"[?] MASTER - poller triggered but not understood: {recv}")



        self.gracefullyKill(tellMaster = False)


class Producer(SetupZMQ):
    def __init__(self, data):

        self.called = False


        self.fails = 0
        self.who = "producer"
        self.data = data
        self.port = data.port
        self.work_list = deque([])
        self.emaildict = []
        self.continueLoop = True
        self.scrapedLength = 0

        try:
            self.connectZMQ()
            self.generatPoller(self.zmqProducer()+[self.masterPUSH])
            self.startLoop()
        except Exception as e:
            logger.exception(f"Failed to initialise ZMQ: {e}.")
            self.health = False
            self.gracefullyKill()

        if self.health:

            self.mainLoop()
        else:
            self.gracefullyKill()



    def startLoop(self):
        logger.debug('[i] PRODUCER - sending ready message to MASTER')
        self.sendToMaster("start")
        logger.debug('[i] PRODUCER - waiting green light from MASTER')
        self.masterSUB.recv_string()

        # while self.health:
        #     socks = dict(self.poller.poll(config.TIMEOUT_CONSTANT))
        #     if socks.get(self.masterPUSH) == zmq.POLLIN:
        #         logger.debug('[i] PRODUCER - waiting green light from MASTER')
        #         self.masterSUB.recv_string()
        #     else:
        #         self.countFails()
    def mainLoop(self):
        logger.info('[i] PRODUCER - starting main loop')
        unscraped = deque([self.data.url])
        scraped = set()
        oldsoup = set()
        queue = 0
        count = 0
        while self.health and self.continueLoop:
            try:
                self.creatWorkList(unscraped, scraped, oldsoup)

                socks = dict(self.poller.poll(100))
                if socks.get(self.masterSUB) == zmq.POLLIN:
                    self.interpretMaster()
                elif socks.get(self.get_sink) == zmq.POLLIN:
                    logger.debug("Receiving data from sink")
                    sink = json.loads(self.get_sink.recv_json())
                    queue -= 1
                    count = sink['count']

                    if not sink['empty']:
                        self.emaildict = self.emaildict + sink['emaildict']
                        for link in sink['linksSet']:
                            if link not in list(scraped) + list(unscraped):
                                unscraped.append(link)

                    logger.info(f"Current scraped {len(scraped)} | Emails found: {len(self.emaildict)}")
                    self.saveResult(self.emaildict, self.data.outputDir)

                elif len(self.work_list):
                    logger.debug(f'PRODUCER - Consuming queue : {queue} | {len(self.work_list)}')
                    while queue <= config.QUEUE and len(self.work_list):
                        work = self.work_list.popleft()
                        queue += 1
                        self.zmq_socket.send_json(json.dumps(work))

                elif count == len(scraped) and queue == 0 and count > 0:
                    logger.info(f'PRODUCER - saving results and quitting')
                    self.masterPUSH.send_json(json.dumps({"name": "producer",
                                                     "state": "done"}))
                    self.saveResult(self.emaildict, self.data.outputDir)
                    break




            except Exception as e:
                logger.exception(f'PRODUCER - Big error, sending kill signal. Reason: {e}')
                self.saveResult(self.emaildict, self.data.outputDir)
                self.health = False

        self.gracefullyKill()

    def creatWorkList(self, unscraped, scraped, oldsoup):
        while len(unscraped) and self.continueLoop:
            if len(scraped) >= self.data.limit-1:
                self.continueLoop = False
            url = unscraped.popleft()
            scraped.add(url)
            work = {
                    "url": url,
                    "oldsoup": list(oldsoup),
                    "domaines": self.data.domains,
                    'scraped': list(scraped),
                    'unscraped': list(unscraped)
                    }
            self.work_list.append(work)
            self.scrapedLength = len(scraped)


    def saveResult(self, dict, dir):
        df = pd.DataFrame(dict, columns=["email", "url"])
        try:
            df.to_csv(os.path.join(dir, "email_list.csv"), index=False)
            logger.debug(f'Emails cached: {len(df)}')
        except Exception as e:
            logger.error(f'Could note save dfs: {e}')

    def workYouBastard(self):
        return self.emaildict, self.scrapedLength

class setParam():
    def __init__(self, param):
        # Format URL
        self.urlsplit = urlsplit(param['url'])
        self.url = f"{self.urlsplit.scheme}://{self.urlsplit.netloc}"
        self.domains = param['domain']
        if __name__ == '__main__':
            self.folder = self.domains[0]
        else:
            self.folder = param['reference'].replace("-", "_")

        # Set constats
        self.workers = param['workers']
        # Set limit
        self.limit = param['limit']
        self.port = 5000 + param['port']

        # set Output
        self.cwd = os.getcwd()
        self.listdir = os.listdir(self.cwd)
        self.outputDir = os.path.join(self.cwd, 'engine/cache', self.folder)
        if not os.path.exists(self.outputDir):
            os.makedirs(self.outputDir)


def processMaster(data):
    master = Master(data)

def processWorker(data):
    worker = Workers(data)

def processSink(data):
    sink = Sink(data)


def main(param):
    KILLING = False


    KILLING2 = False
    original_sigint_handler = signal.signal(signal.SIGINT, signal.SIG_IGN)
    data = setParam(param=param)
    if __name__ == "__main__":
        printParam(data)

    logger.critical(f"######################### NEW JOB: {data.folder} #########################")

    # file_handler_job = logging.FileHandler(os.path.join(data.outputDir, 'log'))
    # file_handler_job.setLevel(logging.INFO)
    # file_handler_job.setFormatter(formatter)
    # logger.addHandler(file_handler_job)


    processes = []
    p = Process(target=processMaster, args=(data,), name="MASTER")
    p.start()
    processes.append(p)
    logger.info('[i] MASTER started')


    for n in range(data.workers):
        p = Process(target=processWorker, args=(data,), name="WORKER")
        p.start()
        processes.append(p)
        logger.info(f'[i] WORKER {n+1}/{data.workers} started')

    p = Process(target=processSink, args=(data,), name="SINK")
    p.start()
    processes.append(p)
    logger.info(f'[i] Sink started')
    ksObj = KillSwitch(data)

    def killswitch(a,b ):
        ksObj()
        ksObj()

    signal.signal(signal.SIGINT, killswitch)
    emails, nmbPgsScraped = Producer(data).workYouBastard()



    logger.info("[i] Finalising, \t")
    for p in processes:
        p.terminate()
    logger.info('[i] Done')

    return emails, nmbPgsScraped


def welcome():
    logo = f"""
$$$$$$$$  $$$$   $$$$  $$$$   $$$$$$     $$$$$$$  $$$$  $$$$    $$$$$$    $$$$$
$$$$$$$$$ $$$$   $$$$  $$$$  $$$$$$$$    $$$$$$$$ $$$$  $$$$  $$$$$$$$$  $$$$$$$
$$$$ $$$$ $$$$   $$$$  $$$$ $$$$  $$$$   $$$$ $$$ $$$$  $$$$ $$$$       $$$$
$$$$$$$$  $$$$   $$$$  $$$$ $$$$$$$$$$   $$$$$$$$ $$$$  $$$$ $$$$ $$$$$$ $$$$$$$
$$$$ $$$$ $$$$   $$$$  $$$$ $$$$         $$$$$$$  $$$$  $$$$ $$$$  $$$$$     $$$$  $$
$$$$$$$$$ $$$$$$$ $$$$$$$$   $$$$        $$$       $$$$$$$$  $$$$$$$$$$  $$$$$$$  $$$$
$$$$$$$$  $$$$$$$  $$$$$$     $$$$$$     $$$        $$$$$$     $$$$$$$    $$$$$    $$

                                                v{config.VERSION} guanicoe
    """
    print(logo)

def printParam(parameters):
    param = f"""
###########################################################################

    Base URL: {parameters.url}
    Domains : {parameters.domains}
    Number workers: {parameters.workers}
    Limit set: {parameters.limit}
    Output: {parameters.outputDir}

###########################################################################
    """

    print(param)

if __name__ == '__main__':
    welcome()

    parser = argparse.ArgumentParser(description="""
    This small utility script was made to crawl websites for email addresses.
    It uses multiprocessing threads to get multiple workers to scrape the web pages,
    extract emails and links, and dumps them in a *.csv file.
    """)
    parser.add_argument('-u', '--url', type=str,
                        required=True, help='Url to crawl')
    parser.add_argument('-d', '--domain', nargs="+", default=False,
                        required=True, help="""Domain name to keep in scope (ex: -d domain1,
                                domain2). The first domain will be used as name
                                for output. """
                        )
    parser.add_argument('-w', '--workers', type=int, default=10,
                        help='Number of workers (default: 10)')
    parser.add_argument('-l', '--limit', type=int, default=1000,
                        help="""Limite the number of pages to crawl
                                (default: 1000)"""
                        )
    parser.add_argument('-o', '--output-dir', type=str,
                        help="""Specify which directory to save the date.
                                (default is URL)"""
                        )
    parser.add_argument('--version', action='version',
                        version=config.VERSION, help='Returns the version number')

    args = parser.parse_args()


    param = {
                "url": args.url,
                "domain": args.domain,
                "reference": str(uuid.uuid4()),
                "workers": args.workers,
                "limit": args.limit,
                "port": 0,
            }

    emails = main(param)
    print(emails)
