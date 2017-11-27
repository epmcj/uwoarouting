###############################################################################
##  Laboratorio de Engenharia de Computadores (LECOM),                       ##
##  Universidade Federal de Minas Gerais (UFMG).                             ##
##                                                                           ##
##  TODO:                                                                    ##
##                                                                           ##
##  Author: Eduardo Pinto                                                    ##
###############################################################################

BROADCAST_ADDR = 0
BASIC_TTL = 100

# Fisrt half of byte
class UOARTypes: 
    COMMON_DATA   = 0x00
    ACK           = 0x01
    # control messages
    INFO_ANNOUN    = 0x02
    SCORE_ANNOUN   = 0x03
    CLUSTER_ANNOUN = 0x04
    ROUTE_ANNOUN   = 0x05
    REQ_SCORE      = 0x06
    REP_SCORE      = 0x07
    UPDATE_INFO    = 0x08
    REQ_RINFO      = 0x09
    REP_RINFO      = 0x0a

# Second half of byte
class UOARFlags:
    ACOUSTIC = 0x10
    WITH_ACK = 0x20

class Message:
    # Basic message
    headerSize = 10 # 4 bytes for each addr + 1 for type + payload length + 
                    # 1 for ttl (time is just for statistics)       
    def __init__(self, src, dst, flags, payload, ctime, ttl):
        self.src   = src
        self.dst   = dst
        self.flags = flags
        self.ctime = ctime # just for statistics
        self.ttl   = ttl
        if hasattr(payload, '__len__'):
            self.payload = payload
        else:
            self.payload = [payload]

    def __len__(self):
        return (self.headerSize + len(self.payload))

    def __str__(self):
        return 'Message from: ' + str(self.src) \
                + ' to ' + str(self.dst) + '.' \
                + ' (len = ' + str(len(self)) + ')'
    
class MessageGenerator:
    # Message that carries data
    def create_acoustic_datamsg(src, dst, payload, ctime, ttl = BASIC_TTL):
        opt = UOARFlags.ACOUSTIC + UOARFlags.WITH_ACK + UOARTypes.COMMON_DATA
        return Message(src, dst, opt, payload, ctime, ttl)
    
    # Message that carries data
    def create_optical_datamsg(src, dst, payload, ctime, ttl = BASIC_TTL):
        opt = UOARFlags.WITH_ACK + UOARTypes.COMMON_DATA
        return Message(src, dst, opt, payload, ctime, ttl)

    # Simple ACK
    def create_acoustic_ack(src, dst, ttl = BASIC_TTL):
        opt = UOARFlags.ACOUSTIC + UOARTypes.ACK
        return Message(src, dst, opt, [], 0, ttl)

    # Simple ACK 
    def create_optical_ack(src, dst, ttl = BASIC_TTL):
        opt = UOARTypes.ACK
        return Message(src, dst, opt, [], 0, ttl)

    # Message for information announcement
    def create_iamsg(src, position, state, hopsToSink, ttl = BASIC_TTL):
        opt = UOARFlags.ACOUSTIC + UOARTypes.INFO_ANNOUN
        return Message(src, BROADCAST_ADDR, opt, \
                       [position, state, hopsToSink], 0, ttl)

    # Message for score announcement
    def create_samsg(src, score, ttl = BASIC_TTL):
        opt = UOARFlags.ACOUSTIC + UOARTypes.SCORE_ANNOUN
        return Message(src, BROADCAST_ADDR, opt, score, 0, ttl)

    # Message for cluster announcement
    def create_camsg(src, ishead, position, ttl = BASIC_TTL):
        opt = UOARFlags.ACOUSTIC + UOARTypes.CLUSTER_ANNOUN
        return Message(src, BROADCAST_ADDR, opt, [ishead, position], 0, ttl)

    # Message to create routes between cluster heads
    def create_ramsg(src, isHead, nextHop, hopsToSink, position, 
                     ttl = BASIC_TTL):
        opt = UOARFlags.ACOUSTIC + UOARTypes.ROUTE_ANNOUN
        return Message(src, BROADCAST_ADDR, opt, [isHead, nextHop, \
                       hopsToSink, position], 0, ttl)
    
    # Message to request neighbors score
    def create_rqsmsg(src, ttl = BASIC_TTL):
        opt = UOARFlags.ACOUSTIC + UOARTypes.REQ_SCORE
        return Message(src, BROADCAST_ADDR, opt, [], 0, ttl)
    
    # Message to reply a score request
    def create_rpsmsg(src, dst, score, ttl = BASIC_TTL):
        opt = UOARFlags.WITH_ACK + UOARTypes.REP_SCORE
        return Message(src, dst, opt, score, 0, ttl)
    
    # Message to inform new cluster head
    def create_uimsg(src, newHead, nextHop, ttl = BASIC_TTL):
        opt = UOARFlags.ACOUSTIC + UOARTypes.UPDATE_INFO
        return Message(src, BROADCAST_ADDR, opt, [newHead, nextHop], 0, ttl)

    # Message to request info about routes that do not contain the dead node.
    def create_rqrmsg(src, deadNode, ttl = BASIC_TTL):
        opt = UOARFlags.ACOUSTIC + UOARTypes.REQ_RINFO
        return Message(src, BROADCAST_ADDR, opt, deadNode, 0, ttl)

    # Message to reply a route info request
    def create_acoustic_rprmsg(src, dst, nextHop, hopsToSink, ttl = BASIC_TTL):
        opt = UOARFlags.ACOUSTIC + UOARFlags.WITH_ACK + UOARTypes.REP_RINFO
        return Message(src, dst, opt, [nextHop, hopsToSink], 0, ttl)
    
    # Message to reply a route info request
    def create_optical_rprmsg(src, dst, nextHop, hopsToSink, ttl = BASIC_TTL):
        opt = UOARFlags.WITH_ACK + UOARTypes.REP_RINFO
        return Message(src, dst, opt, [nextHop, hopsToSink], 0, ttl)