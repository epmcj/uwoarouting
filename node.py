###############################################################################
##  Laboratorio de Engenharia de Computadores (LECOM),                       ##
##  Universidade Federal de Minas Gerais (UFMG).                             ##
##                                                                           ##
##  TODO:                                                                    ##
##  * Verificar se o proximo hop pode ser alcancado no caso de troca de head ##
##  * Melhorar verificacao de status                                         ##
##                                                                           ##
##  Author: Eduardo Pinto                                                    ##
###############################################################################

from messages import MessageGenerator as MG, BASIC_TTL
from messages import BROADCAST_ADDR, Message, UOARFlags, UOARTypes
from modens import AcousticModem as AM
from modens import OpticalModem as OM
from tools import Tools, INFINITY

class UOARState:
    INITIAL        = 0
    CLUSTER_MEMBER = 1
    CLUSTER_HEAD   = 2
    DEAD           = 3 # just for debug

class UOARStatus:
    IDLE        = 0
    DISCOVERING = 1
    ANNOUNCING  = 2
    ELECTING    = 3
    WAITING     = 4
    HEAD_WAIT   = 5
    READY       = 6
    UPDATING    = 7
    RECOVERING  = 8

class Node:
    maxTransmissions = 3
    sinkNodesAddr = [1]
    basicPayload = []
    def __init__(self, addr, x, y, depth, energy, clock, verbose = False):
        assert clock.__class__.__name__ is 'Clock', 'Need a clock object'
        self.verbose = verbose
        self.inbox = []
        self.outbox = [] # pair [msg, number of transmissions]
        self.waitingACK = False
        self.isSink = addr in self.sinkNodesAddr
        self.clock = clock
        # for TDMA
        self.round = 0         
        #
        self.addr      = addr
        self.position  = [x, y, depth]
        # Energy related
        self.energy    = energy
        self.maxEnergy = energy
        self.criticalEnergy = False
        self.energyThresholds = [0.05, 0.2, 0.5]
        self.energyThreshold = energy * self.energyThresholds.pop()
        # for UOAR
        self.state  = UOARState.INITIAL
        self.status = UOARStatus.IDLE 
        self.oneighbors = {}
        self.numReachableNodes = 0
        self.highestScore = [0, INFINITY] # pair [score, addr]
        self.nextHop = None
        self.nextHopDist = INFINITY
        self.hopsToSink = INFINITY
        self.stopWaiting = False
        self.updateStatus = 0 # 0: not updating
                              # 1: update in progress
                              # 2: update done
        self.cheadList = {} # to route phase [addr, is in route]
        self.cmemberList = []
        # self.score  = 0
        self.greaterDistance = 0
        self.avgDistance = 0
        # for possible connection head-member
        self.minHopsToSink = INFINITY
        self.memberAlternative = None
        # for retransmissions
        self.numRetries = 0
        # for recovery (next hop is dead)
        self.msgsLostCount = 0
        self.msgsLostLimit = 2
        self.deadNode      = None
        # for statistics
        self.recvdMsgsCounter = 0
        self.sentMsgsCounter  = 0
        self.avgNumHops = 0
        self.maxNumHops = 0 
        self.avgTimeSpent = 0
        self.maxTimeSpent = 0
        # best for memory
        self.acouticAck = MG.create_acoustic_ack(addr, 0)
        time, _ = Tools.estimate_transmission(self.acouticAck)
        self.acousticAckTime = 2 * time
        self.opticalAck = MG.create_optical_ack(addr, 0)
        time, _ = Tools.estimate_transmission(self.opticalAck)
        self.opticalAckTime = 2 * time

    def move(self, newX, newY, newDepth):
        # Move node to new position.
        self.position[0] = newX
        self.position[1] = newY
        self.position[2] = newDepth

    def application_generate_msg(self):
        # Generates an application message and puts it into the end of the 
        # outbox.
        # assert self.nextHop is not None, 'No next hop found'
        # Simulating the application message as one optical data message.
        msg = MG.create_optical_datamsg(self.addr, 1, self.basicPayload,
                                        self.clock.read()) 
        if self.state is UOARState.CLUSTER_MEMBER:
            end_msg = MG.create_optical_datamsg(self.addr, self.nextHop, msg,
                                                self.clock.read()) 
        else:
            end_msg = MG.create_acoustic_datamsg(self.addr, self.nextHop,
                                                 msg, self.clock.read())
        self.outbox.append([end_msg, 0])

    def calculate_score(self):
        # Calculates node score based on amoung of neighbots and energy level.
        if self.isSink:
            score = INFINITY
        elif self.numReachableNodes is len(self.oneighbors):
            # A node thar can't reach other that is outside its neighbors can't
            # be head.
            score = 0
        else:
            n = int(100 * len(self.oneighbors) / self.numReachableNodes)
            e = int(100 * (self.energy / self.maxEnergy))
            if self.verbose:
                print('E: ' + str(e) + ' N: ' + str(n))
            score = e + n
        return score

    def execute(self, maxTime, isNewSlot):
        # This method is used to simulate the execution of the node. It will
        # return a message, and the required time to transmit it, when the node 
        # wants to communicate.
        msg    = None
        time   = maxTime
        energy = 0

        if self.energy <= 0:
            if self.state is not UOARState.DEAD:
                self.state = UOARState.DEAD
            return time, msg

        if self.isSink is False and self.energy <= self.energyThreshold and \
           (not self.criticalEnergy):
            self.energyThreshold = self.energyThresholds.pop()
            if len(self.energyThresholds) is 0:
                self.criticalEnergy = True
                
            if self.state is UOARState.CLUSTER_HEAD and \
               len(self.cmemberList) is not 0:
                self.updateStatus = 1

        if isNewSlot: # new round
            self.round += 1
            if self.verbose:
                print('Round ' + str(self.round) + ': ' + \
                      str(self.clock.read()))
            # Status machine
            if self.status is UOARStatus.READY:
                if self.msgsLostCount is self.msgsLostLimit:
                    self.status = UOARStatus.RECOVERING
            
            elif self.status is UOARStatus.IDLE:
                self.status = UOARStatus.DISCOVERING

            elif self.status is UOARStatus.DISCOVERING:
                self.status = UOARStatus.ANNOUNCING

            elif self.status is UOARStatus.ANNOUNCING:
                if self.state is UOARState.INITIAL:
                    self.status = UOARStatus.ELECTING
                else:
                    self.status = UOARStatus.READY
                    
            elif self.status is UOARStatus.ELECTING:
                if self.state is UOARState.CLUSTER_MEMBER:
                    self.status = UOARStatus.WAITING
                else:
                    self.status = UOARStatus.HEAD_WAIT
                    
            elif self.status is UOARStatus.WAITING and self.stopWaiting:
                if self.isSink:
                    self.status = UOARStatus.HEAD_WAIT
                else:
                    self.status = UOARStatus.READY
                
            elif self.status is UOARStatus.HEAD_WAIT and self.stopWaiting:
                self.status = UOARStatus.READY
 
            elif self.status is UOARStatus.READY and self.updateStatus is 1:
                self.status = UOARStatus.UPDATING
 
            elif self.status is UOARStatus.UPDATING and self.updateStatus is 0:
                self.status = UOARStatus.READY

            elif self.status is UOARStatus.RECOVERING and \
                 self.deadNode is None and self.msgsLostCount is 0:
                self.status = UOARStatus.READY
                
        if self.state is UOARState.INITIAL:
            if self.status is UOARStatus.DISCOVERING:
                # First stage: announces its own position to the other nodes
                # and then collects info the neighbors for a round.
                if self.isSink:
                    self.hopsToSink = 0
                    self.stopWaiting = False
                msg = MG.create_iamsg(self.addr, self.position, self.state,
                                      self.hopsToSink)
                if self.verbose:
                    print('Node ' + str(self.addr) + ' sending info msg')

            elif self.status is UOARStatus.ANNOUNCING:
                # Second stage: now that the node know its neighbors it can 
                # calculate its score and, if necessary, announce it. If some 
                # of its neighbors is already part of a cluster, then it just
                # join it.
                
                if self.nextHop is not None:
                    if self.hopsToSink is INFINITY:
                        self.state  = UOARState.CLUSTER_MEMBER
                        print('Node ' + str(self.addr) + ' is member 1')
                    else:
                        self.state = UOARState.CLUSTER_HEAD
                        print('Node ' + str(self.addr) + ' is head 1')
                    self.cbrBegin = self.round
                    msg = MG.create_camsg(self.addr, False, self.position)
                    if self.verbose:
                        print('Node ' + str(self.addr) + ' sending cluster msg')
                    self.stopWaiting = False
                    
                else:
                    score = self.calculate_score()
                    if self.highestScore[0] < score:
                        # Maybe received some score before its time to 
                        # calculate.
                        self.highestScore[0] = score
                        self.highestScore[1] = self.addr
                    msg = MG.create_samsg(self.addr, score)
                    if self.verbose:
                        print('Node ' + str(self.addr) + ' sending score msg')

            elif self.status is UOARStatus.ELECTING:
                # Third stage: cluster head election. It will become one if its
                # score is the highest.
                if self.highestScore[1] is self.addr or self.isSink:
                    if self.isSink:
                        if self.verbose:
                            print('Node is sink: ' + str(self.addr))
                    self.state = UOARState.CLUSTER_HEAD
                    ishead = True
                else:
                    self.state = UOARState.CLUSTER_MEMBER
                    self.nextHop = self.highestScore[1]
                    ishead = False
                self.stopWaiting = False
                msg = MG.create_camsg(self.addr, ishead, self.position)
                if self.verbose:
                    print('Node ' + str(self.addr) + ' sending cluster msg')
                
            else:
                raise Exception('Unknown initial status')
            
            time, energy = Tools.estimate_transmission(msg)
            self.energy -= energy
            time = maxTime 

        else:     
            if self.status is UOARStatus.READY:
                # In this stage the node is ready for routing data.
                time, msg = self.send_next_msg(maxTime)
                if msg is None and self.verbose:
                    print('No message')
            
            elif self.status is UOARStatus.WAITING:
                # This stage is necessary for all nodes to walk together.
                pass

            elif self.status is UOARStatus.HEAD_WAIT:
                #
                self.stopWaiting = False
                if self.hopsToSink is not INFINITY:
                    # All head neighbors have received the message of hops
                    if not False in self.cheadList.values():
                        self.stopWaiting = True
                    else:
                        for addr, got in self.cheadList.items():
                            if not got:
                                if self.verbose:
                                    print('Missing node ' + str(addr))
                    
                    msg = MG.create_ramsg(self.addr, True, self.nextHop,  
                                          self.hopsToSink, self.position)
                    if self.verbose:
                        print('Node ' + str(self.addr) + ' sending route msg')
                    time, energy = Tools.estimate_transmission(msg)
                    self.energy -= energy
                    time = maxTime  
                else:
                    if self.memberAlternative is not None:
                        self.hopsToSink = self.minHopsToSink
                        self.nextHop = self.memberAlternative
                        self.stopWaiting = True
                        msg = MG.create_ramsg(self.addr, True, self.nextHop,  
                                              self.hopsToSink, self.position)
                        if self.verbose:
                            print('Node ' + str(self.addr), end=' ')
                            print('sending route msg')
                        time, energy = Tools.estimate_transmission(msg)
                        self.energy -= energy
                        time = maxTime  


            elif self.status is UOARStatus.UPDATING:
                # This stage is used to potentially find another node, with 
                # better score, to be cluster head. 
                if self.updateStatus is 1:
                    # Requests the score of neighbors
                    self.highestScore[0] = self.calculate_score()
                    self.highestScore[1] = self.addr
                    msg = MG.create_rqsmsg(self.addr)
                    self.updateStatus = 2

                elif self.updateStatus is 2:
                    bestCandidate = self.highestScore[1]
                    if bestCandidate is not self.addr:
                        if self.verbose:
                            print('Node ' + str(bestCandidate) + 
                                  ' is the new cluster head')
                        msg = MG.create_uimsg(self.addr,
                                              bestCandidate,
                                              self.nextHop)
                        self.nextHop = bestCandidate
                        self.state = UOARState.CLUSTER_MEMBER
                        # Updating lists
                        self.cheadList[bestCandidate] = True
                        self.cmemberList.remove(bestCandidate)
                    self.updateStatus = 0
                
                if msg is not None:
                    time, energy = Tools.estimate_transmission(msg)
                    self.energy -= energy
                    time = maxTime  

            elif self.status is UOARStatus.RECOVERING:
                #
                if self.deadNode is None:
                    # First round in recovering
                    self.deadNode = self.nextHop
                    self.hopsToSink = INFINITY
                    self.numReachableNodes -= 1
                else:
                    if self.nextHop is self.deadNode:
                        # Node didn't receive any message from cluster
                        self.state = UOARState.CLUSTER_HEAD

                # Updating lists
                if self.deadNode in self.cheadList:
                    del self.cheadList[self.deadNode]
                if self.deadNode in self.cmemberList:
                    self.cmemberList.remove(self.deadNode)
                if self.deadNode in self.oneighbors:
                    del self.oneighbors[self.deadNode]

                if self.state is UOARState.CLUSTER_MEMBER:
                    if len(self.oneighbors) is 0:
                        # if there are no more neighbors
                        self.state = UOARState.CLUSTER_HEAD

                if self.nextHop is not self.deadNode:
                    # Find some new next hop.
                    ishead = self.state is UOARState.CLUSTER_HEAD
                    if ishead:
                        msg = MG.create_camsg(self.addr, ishead, self.position)
                        time, energy = Tools.estimate_transmission(msg)
                    self.msgsLostCount = 0
                    self.deadNode = None
                else:              
                    msg = MG.create_rqrmsg(self.addr, self.deadNode)
                    time, energy = Tools.estimate_transmission(msg)
                time = maxTime  
                self.energy -= energy
                    
            else:
                raise Exception('Unknown cluster status')
        
        return time, msg

    def send_next_msg(self, remainingTime):
        # Sends the first message in the outbox if the time and energy are 
        # sufficient. Returns the sent message and the required time to 
        # transmit it (when the message requires an ack, the time is the sum
        # of both transmissions times - message and ack.) 
        energy = 0
        time = 0
        msg = None
        if len(self.outbox) is not 0:
            while self.outbox[0][1] is self.maxTransmissions:
                # Reached the maximum number of transmissions allowed. 
                # Discard it and move on. Must check if the outbox got empty.
                if self.verbose:
                    print('(!) DROPPING MESSAGE')
                dmsg = (self.outbox.pop(0))[0]
                if (dmsg.flags & 0x0f) is UOARTypes.COMMON_DATA:
                    self.msgsLostCount += 1
                self.waitingACK = False
                if self.msgsLostCount is self.msgsLostLimit or \
                   len(self.outbox) is 0:
                    return time, msg
            # Will only sends a message if there is enough time and energy
            pair = self.outbox[0]
            nextMsg = pair[0]
            if (nextMsg.flags & 0x0f) is UOARTypes.COMMON_DATA:
                # Just the get the must updated next hop. (is useful when a 
                # next hop node dies)
                nextMsg.dst = self.nextHop
                if self.state is UOARState.CLUSTER_HEAD: 
                    # Must be update beacuse next hop may have changed and the
                    # node changed its state.
                    nextMsg.flags |= UOARFlags.ACOUSTIC 
                else:
                    nextMsg.flags &= ~UOARFlags.ACOUSTIC 
                
            etime, eenergy = Tools.estimate_transmission(nextMsg)
            if nextMsg.dst is BROADCAST_ADDR:
                if etime < remainingTime and eenergy < self.energy:
                    # Broadcasts do not need ACK so they only got send once.
                    msg = nextMsg
                    self.outbox.pop(0)
                    self.energy -= eenergy
                    time = etime
                else:
                    if self.verbose:
                        print('time is not enough')
            elif  nextMsg.flags & UOARFlags.WITH_ACK:
                # Needs time to possibly receive the ACK.
                # Supposing that ack size is at maximum 2 * header size.
                if (nextMsg.flags & UOARFlags.ACOUSTIC):
                    etimeAck = etime + self.acousticAckTime
                else:
                    etimeAck = etime + self.opticalAckTime
                if etimeAck < remainingTime and energy < self.energy:
                    msg = nextMsg
                    self.outbox[0][1] += 1
                    self.waitingACK = True
                    self.energy -= eenergy
                    time = etime
                else:
                    if self.verbose:
                        print('time is not enough (' + str(remainingTime) + ')')
            else: 
                if self.verbose:
                    print('unknown message')
        else:
            if self.verbose:
                print('Empty outbox')
        # Just for statistics
        if msg is not None and (msg.flags & 0x0f) is UOARTypes.COMMON_DATA:
            self.sentMsgsCounter += 1

        # if msg is not None:
        #     print('tipo: ' + str(msg.flags & 0x0f), end=' ')
        #     if msg.flags & UOARFlags.ACOUSTIC:
        #         print('acoustic', end=' ')
        #         print('energy ' + str(self.energy), end=' ')
        #         print('inbox ' + str(len(self.outbox)))
        #     else:
        #         print('optical', end=' ')
        #         print('energy ' + str(self.energy), end=' ')
        #         print('inbox ' + str(len(self.outbox)))

        return time, msg

    def recv_msg(self, recvMsg):
        #
        msg  = None
        time = 0
        if recvMsg.flags & UOARFlags.ACOUSTIC:
            recvTime = (len(recvMsg) * 8) / AM.transmssionRate
            energyToRecv = recvTime * AM.rxPowerConsumption
        else:
            recvTime = (len(recvMsg) * 8) / OM.transmssionRate
            energyToRecv = recvTime * OM.rxPowerConsumption
        if self.energy >= energyToRecv:
            self.energy -= energyToRecv
            self.handle_message(recvMsg)
            if recvMsg.flags & UOARFlags.WITH_ACK:
                # Generating ack to send
                if self.verbose:
                    print('Sending ACK')
                if recvMsg.flags & UOARFlags.ACOUSTIC:
                    #ack = MG.create_acoustic_ack(self.addr, recvMsg.src)
                    ack = self.acouticAck
                    ack.dst = recvMsg.src
                else:
                    #ack = MG.create_optical_ack(self.addr, recvMsg.src)
                    ack = self.opticalAck
                    ack.dst = recvMsg.src
                etime, energy = Tools.estimate_transmission(ack)
                if self.energy > energy:
                    msg  = ack
                    time = etime
                    self.energy -= energy
        else:
            if self.verbose:
                print('Missing energy (' + str(self.energy) + '|' +
                      str(energyToRecv) + ')')
        return time, msg

    def handle_message(self, msg):
        # Handles the received messages acording to their types.
        msgType = msg.flags & 0x0f # first half is the type

        if msgType is UOARTypes.COMMON_DATA:
            if self.verbose:
                print('Handling data message from node ' + str(msg.src))

            innerMsg = msg.payload
            innerMsg.ttl -= 1
            if innerMsg.dst is not self.addr:
                if innerMsg.ttl is not 0:
                    if self.state is UOARState.CLUSTER_MEMBER:
                        msg = MG.create_optical_datamsg(self.addr,
                                                        self.nextHop,
                                                        innerMsg,
                                                        self.clock.read())
                    else:
                        msg = MG.create_acoustic_datamsg(self.addr,
                                                         self.nextHop,
                                                         innerMsg,
                                                         self.clock.read())
                    self.outbox.append([msg, 0])
                else:
                    if self.verbose:
                        print('Message droped (TTL reached 0)')
            self.recvdMsgsCounter += 1
            if self.isSink is True:
                # Hops statistics
                corrCoeff = (self.recvdMsgsCounter - 1) / self.recvdMsgsCounter
                numHops = BASIC_TTL - innerMsg.ttl
                if numHops > self.maxNumHops:
                    self.maxNumHops = numHops
                self.avgNumHops *= corrCoeff
                self.avgNumHops += (numHops / self.recvdMsgsCounter) 
                # Time statistics
                time = self.clock.read() - innerMsg.ctime
                if self.verbose:
                    print('Received (time: ' + str(time) + ')')
                if time > self.maxTimeSpent:
                    self.maxTimeSpent = time
                self.avgTimeSpent *= corrCoeff
                self.avgTimeSpent += (time / self.recvdMsgsCounter)

        elif msgType is UOARTypes.INFO_ANNOUN:
            if self.verbose:
                print('Handling info message from node ' + str(msg.src))

            self.numReachableNodes += 1
            nodePosition  = msg.payload[0]
            nodeState = msg.payload[1]
            nodeHops = msg.payload[2]
            distFromNode = Tools.distance(self.position, nodePosition)
            # Adding in lists
            if nodeState is UOARState.CLUSTER_HEAD:
                self.cheadList[msg.src] = nodeHops is not INFINITY
            if distFromNode <= OM.maxrange:
                self.oneighbors[msg.src] = nodePosition
                if nodeState is UOARState.CLUSTER_MEMBER and \
                   msg.src not in self.cmemberList:
                    self.cmemberList.append(msg.src)
            updtFactor = (self.numReachableNodes - 1) / self.numReachableNodes
            self.avgDistance = self.avgDistance * updtFactor
            self.avgDistance += (distFromNode / self.numReachableNodes)
            if distFromNode > self.greaterDistance:
                self.greaterDistance = distFromNode

            if self.state is UOARState.INITIAL and not self.isSink:
                # If it is not in a cluster and some neighbor is already
                # member or a head, join it. It's preferable to join as
                # a member than as a head. 
                if distFromNode <= OM.maxrange:
                    if nodeState is not UOARState.INITIAL:
                        currDist = INFINITY
                        if self.nextHop in self.oneighbors:
                            nextPos = self.oneighbors[self.nextHop]
                            currDist = Tools.distance(self.position, nextPos)
                        if distFromNode < currDist:
                            self.nextHop = msg.src
                            self.hopsToSink = INFINITY

                else:
                    if nodeState is UOARState.CLUSTER_HEAD:
                        if self.hopsToSink is INFINITY:
                            if self.nextHop is None:
                                self.nextHop = msg.src
                                self.hopsToSink = nodeHops + 1
                        else:
                            if (nodeHops + 1) < self.hopsToSink:
                                self.nextHop = msg.src
                                self.hopsToSink = nodeHops + 1

            if (self.state is not UOARState.INITIAL and \
               self.status is not UOARStatus.DISCOVERING) and \
               nodeState is UOARState.INITIAL:
                # When a node enters in the network and needs information.
                # Routing control messages have higher priority than data 
                # messages.
                msg = MG.create_iamsg(self.addr, self.position, self.state,
                                      self.hopsToSink)
                # Insert the message in que outbox or updates the next ot 
                # be sent. 
                if len(self.outbox) is not 0:
                    firstMsgType = self.outbox[0][0].flags & 0x0f
                    if firstMsgType is not UOARTypes.INFO_ANNOUN:
                        self.outbox.insert(0, [msg, 0])
                    else:
                        self.outbox[0] = [msg, 0]
                else:
                    self.outbox.insert(0, [msg, 0])

        elif msgType is UOARTypes.SCORE_ANNOUN or \
             msgType is UOARTypes.REP_SCORE:
            if self.verbose:
                print('Handling score message from node ' + str(msg.src))
            
            nodeScore = msg.payload[0]
            if msg.src in self.oneighbors and \
               (self.status is UOARStatus.ANNOUNCING or \
               self.status is UOARStatus.DISCOVERING or \
               self.status is UOARStatus.UPDATING):
                # Cluster heads are nodes with the highest score amoung its 
                # neighbors (in case of a tie, the node with lowest addr wins) 
                if (self.highestScore[0] < nodeScore) or \
                   (self.highestScore[0] == nodeScore and \
                    self.highestScore[1] > msg.src):
                    self.highestScore = [nodeScore, msg.src]

        elif msgType is UOARTypes.CLUSTER_ANNOUN:
            if self.verbose:
                print('Handling cluster message from node ' + str(msg.src))
            
            nodeIsHead = msg.payload[0]
            if nodeIsHead:
                # A cluster head node will send its own address in the cluster
                # announcement payload
                if msg.src not in self.cheadList:
                    if self.status is UOARStatus.ELECTING or \
                       self.status is UOARStatus.ANNOUNCING: 
                        self.cheadList[msg.src] = False
                    else:
                        self.cheadList[msg.src] = True
                        
                if msg.src in self.cmemberList:
                    self.cmemberList.remove(msg.src)
            else:
                if msg.src in self.oneighbors and \
                   msg.src not in self.cmemberList:
                    self.cmemberList.append(msg.src)
                    if msg.src in self.cheadList:
                        del self.cheadList[msg.src]

            if msg.src in self.oneighbors and \
               self.status is UOARStatus.DISCOVERING:
                self.nextHop = msg.src

        elif msgType is UOARTypes.ROUTE_ANNOUN:
            if self.verbose:
                print('Handling route message from node ' + str(msg.src))
            nodeIsHead   = msg.payload[0]
            nodeNextHop  = msg.payload[1]
            nodeHops     = msg.payload[2] + 1
            nodePosition = msg.payload[3]
            if self.state is UOARState.CLUSTER_HEAD:
                if nodeIsHead:
                    dist = Tools.distance(self.position, nodePosition)
                    self.cheadList[msg.src] = True
                    if self.hopsToSink > nodeHops or \
                       (self.hopsToSink == nodeHops and \
                       dist < self.nextHopDist):
                        self.hopsToSink  = nodeHops
                        self.nextHop     = msg.src
                        self.nextHopDist = dist
                        
                elif self.isSink is False:
                    if nodeHops < self.minHopsToSink:
                        self.minHopsToSink = nodeHops
                        self.memberAlternative = msg.src

                    if self.nextHop is not None and \
                       nodeNextHop is not self.addr:
                        if msg.src in self.oneighbors and \
                           nodeHops <= (self.hopsToSink + 1):
                            # better be a member than a head 
                            # print('Node ' + str(self.addr) + ' was member 2')
                            # print(nodeIsHead)
                            # print(nodeNextHop)
                            # print(nodeHops)
                            # print(nodePosition)
                            # print(self.hopsToSink + 1)
                            self.state = UOARState.CLUSTER_MEMBER
                            self.nextHop = msg.src
                            self.hopsToSink = nodeHops
                            newMsg = MG.create_camsg(self.addr, False,
                                                     self.position)
                            self.outbox.insert(0, [newMsg, 0])

            if (self.status is UOARStatus.WAITING or \
               self.status is UOARStatus.ELECTING) and \
               self.nextHop is msg.src:
               # For members
                if nodeHops < self.minHopsToSink:
                    self.minHopsToSink = nodeHops
                    newMsg = MG.create_ramsg(self.addr, False, self.nextHop, 
                                             nodeHops, self.position)
                    self.outbox.insert(0, [newMsg, 0])
                self.stopWaiting = True  

        elif msgType is UOARTypes.REQ_SCORE:
            if self.verbose:
                print('Handling req score msg from ' + str(msg.src))

            if msg.src in self.oneighbors:
                # self.score = self.calculate_score()
                # newMsg = MG.create_rpsmsg(self.addr, msg.src, self.score)
                score = self.calculate_score()
                newMsg = MG.create_rpsmsg(self.addr, msg.src, score)
                if len(self.outbox) is not 0:
                    firstMsgType = self.outbox[0].flags & 0x0f
                    if firstMsgType is not UOARTypes.REP_SCORE:
                        self.outbox.insert(0, [newMsg, 0])
                    else:
                        self.outbox[0] = [newMsg, 0]
                else:
                    self.outbox.append([newMsg, 0])

        elif msgType is UOARTypes.UPDATE_INFO:
            if self.verbose:
                print('Handling update info msg from ' + str(msg.src))

            newHead = msg.payload[0]
            newNextHop = msg.payload[1]
            if newHead is self.addr:
                # Must be a head now
                self.state = UOARState.CLUSTER_HEAD
                self.nextHop = newNextHop
            else:
                if self.nextHop is msg.src or newHead in self.oneighbors:
                    # Must update which node is the next hop
                    ##################################################
                    ## Might be a problem is new head is out of range
                    ##################################################
                    self.nextHop = newHead
                self.cheadList[newHead] = True

            if newHead in self.oneighbors:
                self.cmemberList.remove(msg.payload[0])

            if msg.src in self.oneighbors:
                self.cmemberList.append(msg.src)

            del self.cheadList[msg.src]

            if self.verbose:
                print(self.cheadList)
                print(self.cmemberList)

        elif msgType is UOARTypes.REQ_RINFO:
            if self.verbose:
                print('Handling route info request msg from ' + str(msg.src))

            if msg.src is not self.nextHop and \
               msg.payload[0] is not self.nextHop:
                # Only replies if the requester is not its own next hop and  
                # they don't share the same next hop. (-_- can't help)
                
                if msg.src in self.oneighbors:
                    newMsg = MG.create_optical_rprmsg(self.addr, msg.src,
                                                      self.nextHop,
                                                      self.hopsToSink)
                else:
                    newMsg = MG.create_acoustic_rprmsg(self.addr, msg.src,
                                                       self.nextHop,
                                                       self.hopsToSink)
                self.outbox.insert(0, [newMsg, 0])        

        elif msgType is UOARTypes.REP_RINFO:
            if self.verbose:
                print('Handling route info reply from ' + str(msg.src))

            if self.status is UOARStatus.RECOVERING:
                nodeNextHop = msg.payload[0]
                nodeHopsToSink = msg.payload[1]
                replier = msg.src
                if replier in self.oneighbors:
                    self.nextHop = msg.src
                    self.hopsToSink = INFINITY
                    print('Node ' + str(self.addr) + ' was member 3')
                    self.state = UOARState.CLUSTER_MEMBER

                if self.state is UOARState.CLUSTER_HEAD and \
                   self.hopsToSink >= nodeHopsToSink:
                    self.nextHop = msg.src
                    self.hopsToSink = nodeHopsToSink + 1

        elif msgType is UOARTypes.ACK:
            if self.verbose:
                print('Handling ACK from node ' + str(msg.src))

            if self.waitingACK:
                self.outbox.pop(0)
                self.waitingACK = False
                if self.msgsLostCount is not 0:
                    self.msgsLostCount = 0
            else:
                if self.verbose:
                    print('error: unknown ack received')

        else:
            if self.verbose:
                print('unknown message type')
