#!/usr/bin/python3
# encoding: utf-8
# Crawler
# By Guanicoe
# guanicoe@pm.me
# https://github.com/guanicoe/crawler
import zmq
import json
import time
#Custom modules
import config

import logging

# DEBUG: Detailed information, typically of interest only when diagnosing problems.

# INFO: Confirmation that things are working as expected.

# WARNING: An indication that something unexpected happened, or indicative of some problem in the near future (e.g. ‘disk space low’). The software is still working as expected.

# ERROR: Due to a more serious problem, the software has not been able to perform some function.

# CRITICAL: A serious error, indicating that the program itself may be unable to continue running.

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

formatter = logging.Formatter('%(levelname)s:%(module)s:%(name)s:%(funcName)s --- %(message)s --- [%(lineno)d]')

file_handler = logging.FileHandler('logs/general.log')
file_handler.setLevel(logging.WARNING)
file_handler.setFormatter(formatter)


stream_handler = logging.StreamHandler()
stream_handler.setLevel(logging.DEBUG)
stream_handler.setFormatter(formatter)

logger.addHandler(file_handler)
logger.addHandler(stream_handler)


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

        self.zmq_socket = context.socket(zmq.PUSH)
        self.zmq_socket.bind(f"tcp://127.0.0.1:{port+2}")#5557")
        logger.debug(f"Successful connection to zmq_socket on port {self.port+2} - {self.zmq_socket}")

        self.get_sink = context.socket(zmq.PULL)
        self.get_sink.connect(f"tcp://127.0.0.1:{port+3}")#5559")
        logger.debug(f"Successful connection to get_sink on port {self.port+3} - {self.get_sink}")

        return [self.zmq_socket, self.get_sink ]

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
            self.sendToMaster("stop")
        logger.critical(f"Killing process: {self.who}")
        # self.masterPUSH.close()
        # self.masterSUB.close()
        # self.work_receiver.close()
        # self.consumer_sender.close()
        # self.context.term()
        self.context.destroy(linger=0)
        logger.critical(f"Process: {self.who} killed!")

    def interpretMaster(self):
        recv = self.masterSUB.recv_string()
        if recv.split(' ')[1] == 'kill':
            logger.critical('Closing service, received kill signal from masterSUB')
            self.health = False
        else:
            logger.error(f'Received unknown message from masterSUB: {recv}')

    def countFails(self):
        self.fails += 1
        logger.warning(f"The {self.who}'s poller socket has timedout {self.fails} time(s) in a row.")
        if self.fails >= 5:
            logger.critical(f"The {self.who}'s poller socket has timedout {self.fails} times in a row and is being killed.")
            self.health = False


class Workers(SetupZMQ):
    def __init__(self, data):

        self.data = {"state": False}

        self.fails = 0
        self.who = "worker"
        self.port = data['port']

        try:
            self.connectZMQ()
            self.generatPoller(self.zmqWorker())
        except Exception as e:
            logger.exception(f"Failed to initialise ZMQ: {e}.")
            self.health = False

        if self.health:
            self.sendToMaster("start")
            self.mainLoop()
        else:
            self.gracefullyKill()


    def mainLoop(self):
        while self.health:
            socks = dict(self.poller.poll(20e3))
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
                    if extension not in config.BLACKLIST['EXTENSIONS']:
                        data = creatSoup(work)
                        if data['state']:
                            linksSet, emailsSet = readhtml(data['response'], work, config.BLACKLIST['URLS'],  config.RGX)
                            output = {
                                        "initUrl": work['url'],
                                        "emaildict": [{"email": email, "url": work['url']} for email in emailsSet],
                                        "linksSet": linksSet,
                                        "oldsoup": data['oldsoup'],
                                        "empty": False,
                                        "error": False,
                                    }
                except Exception as e:
                     output['error'] = True
                     logger.warning(f'Exception hit when undertaking job {e}. Work: {work}')

                consumer_sender.send_json(json.dumps(output))

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
        self.port = data['port']

        try:
            self.connectZMQ()
            self.generatPoller(self.zmqSink())
        except Exception as e:
            logger.exception(f"Failed to initialise ZMQ: {e}.")
            self.health = False

        if self.health:
            self.sendToMaster("start")
            self.mainLoop()
        else:
            self.gracefullyKill()

    def mainLoop(self):
        while self.health:
            socks = dict(self.poller.poll(30e3))
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
        self.port = data['port']

        self.workers = data['workers']


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
                        logger.debug(f"{self.count}/{self.workers} worker connected")
                    elif recv == {'name': 'sink', 'state': 'start'}:
                        logger.debug(f"Sink connected")
                        self.sink = True
                    elif recv == {'name': 'producer', 'state': 'start'}:
                        logger.debug(f"Producer connected")
                        self.producer = True
            elif self.count == self.workers and self.sink and self.producer:
                logger.critical(f"[+] MASTER - Let's go!")
                break


    def mainLoop(self):

        self.socketPUB.send_string("producer go")

        while self.health:
            socks = dict(self.poller.poll(1000))
            if socks.get(self.masterPULL) == zmq.POLLIN:
                recv = json.loads(self.masterPULL.recv_json())
                if recv == {'name': 'producer', 'state': 'done'}:
                    logger.critical(f"[i] MASTER - received quit message from {recv['name']}")
                    self.pubKillSockets(['worker', 'sink'])
                    break
                elif recv == {'name': 'worker', 'state': 'quit'}:
                    logger.critical(f"[i] MASTER - received quit message from {recv['name']}")
                    self.pubKillSockets(['producer', 'worker', 'sink'])
                    break
                elif recv == {'name': 'sink', 'state': 'quit'}:
                    logger.critical(f"[i] MASTER - received quit message from {recv['name']}")
                    self.pubKillSockets(['producer', 'worker'])
                    break
                else:
                    logger.error(f"[?] MASTER - poller triggered but not understood: {recv}")



        self.gracefullyKill(tellMaster = False)


class Producer(SetupZMQ):
    def __init__(self, data):
        self.fails = 0
        self.who = "poducer"
        self.data = data
        self.port = data['port']
        self.work_list = deque([])
        self.emaildict = []
        self.continueLoop = True

        try:
            self.connectZMQ()
            self.generatPoller(self.zmqProducer())
        except Exception as e:
            logger.exception(f"Failed to initialise ZMQ: {e}.")
            self.health = False

        logging.debug('[i] PRODUCER - sending ready message to MASTER')
        self.masterPUSH.send_json(json.dumps({"name": "producer", "state": "start"}))

        logging.debug('[i] PRODUCER - waiting green light from MASTER')
        self.masterSUB.recv_string()

        if self.health:
            self.startLoop()
            self.mainLoop()
        else:
            self.gracefullyKill()

        return self.emaildict

    def mainLoop(self):
        logging.info('[i] PRODUCER - starting main loop')
        unscraped = deque([self.data.url])
        scraped = set()
        oldsoup = set()
        queue = 0
        count = 0

        while self.health and self.continueLoop:
            try:
                self.creatWorkList(self, unscraped, scraped, oldsoup)

                socks = dict(poller.poll(100))
                if socks.get(self.get_sink) == zmq.POLLIN:
                    logger.debug("Receiving data from sink")
                    sink = json.loads(self.get_sink.recv_json())
                    queue -= 1
                    count = sink['count']

                    if not sink['empty']:
                        self.emaildict = self.emaildict + sink['emaildict']
                        for link in sink['linksSet']:
                            if link not in list(scraped) + list(unscraped):
                                unscraped.append(link)
                                logger.debug(f"Updating unscraped set. New length {len(unscraped)}")

                    saveResult(self.emaildict, data.outputDir)

                elif len(self.work_list):
                    logging.debug(f'PRODUCER - Consuming queue')
                    while queue < config.QUEUE and len(self.work_list):
                        work = self.work_list.popleft()
                        queue += 1
                        self.zmq_socket.send_json(json.dumps(work))

                elif count == len(scraped) and queue == 0:
                    logging.debug(f'PRODUCER - saving results and quitting')
                    self.masterPUSH.send_json(json.dumps({"name": "producer",
                                                     "state": "done"}))
                    saveResult(emaildict, data.outputDir, printRes=True)
                    break


                elif socks.get(self.masterSUB) == zmq.POLLIN:
                    self.interpretMaster()

            except Exception as e:
                logging.critical(f'[{n}] PRODUCER - Big error, sending kill signal. Reason: {e}')
                self.saveResult(self.emaildict, data.outputDir)
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


    def saveResult(self, dict, dir):
        df = pd.DataFrame(dict, columns=["email", "url"])
        try:
            df.to_csv(os.path.join(dir, "email_list.csv"), index=False)
            logger.debug(f'Emails cached: {len(df)}')
        except Exception as e:
            logger.error(f'Could note save dfs: {e}')






if __name__ == '__main__':
    data = {"port" : 20, "workers": 2}
    # worker = Workers(data)
    # sink = Sink(data)
    sink = Master(data)
