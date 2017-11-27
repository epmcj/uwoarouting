###############################################################################
##  Laboratorio de Engenharia de Computadores (LECOM),                       ##
##  Universidade Federal de Minas Gerais (UFMG).                             ##
##                                                                           ##
##  TODO:                                                                    ##
##                                                                           ##
##  Author: Eduardo Pinto                                                    ##
###############################################################################

from channels import AcousticChannel, OpticalChannel
from messages import *
from modens import AcousticModem as AM
from modens import OpticalModem as OM
from node import Node
from tools import Tools, Clock, INFINITY


class Simulator:
    beta = 0
    def __init__(self, verbose = False):
        self.packetSize   = 0
        self.timeInterval = None
        # channels
        self.achannel = AcousticChannel(k = 2.0, s = 0.0, w = 0.0)
        self.ochannel = OpticalChannel(c  = 4.3e-2, T = 298.15, \
                                       S = OM.sensitivity, \
                                       R = OM.shuntResistance, \
                                       Id = OM.maxDarkCurrent, \
                                       Il = OM.incidentCurrent, \
                                       Ar = OM.Ar, At = OM.At, \
                                       bw = OM.bandWidth, \
                                       theta = OM.beamDivergence)
        # application parameters
        self.appStart    = INFINITY
        self.appInterval = INFINITY
        self.appStop     = INFINITY 
        # control
        self.clock = Clock()
        self.verbose = verbose
        self.firstNode = 0
        # node control
        self.nodesUpdated = True
        self.numNodes   = 0
        self.nodesRef   = {} # __
        self.aneighbors = {} # __
        self.oneighbors = {} # __
        # statistics
        self.atransmissions = 0
        self.otransmissions = 0

    def create_node(self, addr, x, y, depth, energy):
        #
        assert addr is not BROADCAST_ADDR, 'Node can\' t have broadcast addr'
        node = Node(addr, x, y, depth, energy, self.clock, self.verbose)
        self.nodesRef[addr] = node
        self.nodesUpdated = False
    
    def add_node(self, node):
        #
        assert node.__class__.__name__ is 'Node', 'Node must be of class Node'
        assert node.addr is not BROADCAST_ADDR, 'Node addr is invalid (addr=0)'
        self.nodesRef[node.addr] = node
        self.nodesUpdated = False

    # necessary for broadcast
    def update_nodes_info(self):
        if self.verbose: 
            print('Updating nodes information')
        self.numNodes = len(self.nodesRef)
        for addr1 in self.nodesRef.keys():
            aneighbors = []
            oneighbors = []
            for addr2 in self.nodesRef.keys():
                if addr1 is not addr2:
                    node1 = self.nodesRef[addr1]
                    node2 = self.nodesRef[addr2]
                    distance = Tools.distance(node1.position, node2.position)
                    if distance <= AM.maxrange:
                        aneighbors.append(addr2)
                    if distance <= OM.maxrange:
                        oneighbors.append(addr2)
            self.aneighbors[addr1] = aneighbors
            self.oneighbors[addr1] = oneighbors

    def create_app_msgs(self):
        # Method to feed the routing algorithm with application messages.
        for node in self.nodesRef.values():
            if node.energy > 0 and node.isSink is False:
                node.application_generate_msg()

    def print_data(self):
        print('Time: ' + str(self.clock.read()))
        print('Number of acoustic transmissions: ' + str(self.atransmissions))
        print('Number of optical transmissions: ' + str(self.otransmissions))

    def start(self, stopExec):
        assert (stopExec > 0), 'Execution time must be > 0' 
        assert (self.packetSize > 0), 'Packet size can not be <= 0'
        assert (len(self.nodesRef) is not 0), 'Missing nodes' 
        assert (self.appStart is not INFINITY), 'Missing app start time'
        assert (self.appInterval is not INFINITY), 'Missing app interval time'
        assert (self.appStop > self.appStart), 'Stop time must be > start time'

        if not self.clock.alarm_is_on():
            self.clock.set_alarm(self.create_app_msgs, self.appStart, \
                                 self.appInterval, self.appStop)
        
        if self.timeInterval is None:
            # If any time interval is informed, then it calculates the minimum
            # time required (acoustic transmission with ack).
            self.timeInterval = 1.5 * (self.packetSize * 8) / AM.transmssionRate 
            print('Time interval: ' + str(self.timeInterval))
        # Updating node information because some node was recently added
        if not self.nodesUpdated:
            self.update_nodes_info()
        # Creating a basic payload to avoid large memory usage
        payloadSize = self.packetSize - (2 * Message.headerSize)
        basicPayload = list(x for x in range(0, payloadSize))
        for node in self.nodesRef.values():
            node.timeInterval = self.timeInterval
            node.cbrInterval  = self.appInterval
            node.basicPayload = basicPayload
        nodesList = list(self.nodesRef.values())
        numSlots = int(stopExec/self.timeInterval)
        print('Simulation started')
        for slot in range(0, numSlots):
            # Choosing the node that will trasmit in this time slot 
            # (in ascending order)
            currNode = (self.firstNode + slot) % self.numNodes
            node = nodesList[currNode]
            if self.verbose:
                print('::Time slot of node ' + str(node.addr))
            # If the node is out of energy, then just skip its time.
            if node.energy <= 0:
                if self.verbose:
                    print('Node ' + str(node.addr) + ' zZzz')
                self.clock.run(self.timeInterval)
                continue
            remainingTime = self.timeInterval
            beginTimeSlot = True
            while remainingTime > 0:
                # message is transmitted by the node
                timeSpent, msg = node.execute(remainingTime, beginTimeSlot)
                # _, msg = node.execute(remainingTime, beginTimeSlot)
                beginTimeSlot = False
                if msg is None:
                    if self.verbose:
                        print('No more messages')
                    self.clock.run(remainingTime)
                    break
                remainingTime -= timeSpent
                self.clock.run(timeSpent)
                # data in message header
                isAcoustic = (msg.flags & UOARFlags.ACOUSTIC)
                needACK = (msg.flags & UOARFlags.WITH_ACK)
                if msg.dst == BROADCAST_ADDR:
                    assert isAcoustic, 'Optical broadcasts are not allowed'
                    destinations = self.aneighbors[msg.src]
                    self.atransmissions += 1
                else:
                    destinations = [msg.dst]
                # sending messages
                for dst in destinations:
                    if self.verbose:
                        print('Sending message to ' + str(dst))
                    srcPos = self.nodesRef[msg.src].position
                    dstPos = self.nodesRef[dst].position
                    dist = Tools.distance(srcPos, dstPos)
                    # checking if the transmission was successful
                    if isAcoustic:
                        success = self.achannel.use(AM.frequency, \
                                                    AM.txPower, \
                                                    dist, \
                                                    len(msg))
                        self.atransmissions += 1
                    else:
                        success = self.ochannel.use(OM.txPower, dist, \
                                                    dist, self.beta, \
                                                    len(msg))
                        self.otransmissions += 1
                    # If the transmission succed, then destination node receive 
                    # the message and may send an ack
                    if success:
                        # Getting ack and time spent sending it (if sent)
                        if self.verbose:
                            print('Receiving message')
                        ackTime, ack = self.nodesRef[dst].recv_msg(msg)
                        # Removing time, if required.
                        if needACK:
                            if isAcoustic:
                                ackTime = self.nodesRef[dst].acousticAckTime
                            else:
                                ackTime = self.nodesRef[dst].opticalAckTime
                            remainingTime -= ackTime
                            self.clock.run(ackTime)
                        # Sending ack.
                        if needACK and ack is not None:
                            if isAcoustic:
                                success = self.achannel.use(AM.frequency, \
                                                            AM.txPower, \
                                                            dist, \
                                                            len(ack))
                                self.atransmissions += 1
                            else: 
                                success = self.ochannel.use(OM.txPower, dist, \
                                                            dist, self.beta, \
                                                            len(ack))
                                self.otransmissions += 1
                            if success:
                                self.nodesRef[ack.dst].recv_msg(ack)
                            else:
                                if self.verbose:
                                    print('Failed to send ACK')
                        elif needACK:
                            if self.verbose:
                                print('Failed to ack')
                    else:
                        if self.verbose:
                            print('Failed to send')
            assert remainingTime >= 0, 'error: time interval was not ' + \
                                       'respected by node ' + str(node.addr) + \
                                       ' (' + str(remainingTime) + ')'
        self.firstNode = currNode + 1 # saving for possible future executions
        print('Simulation finished')
        self.print_data()
