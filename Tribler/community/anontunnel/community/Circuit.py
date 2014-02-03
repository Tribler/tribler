from Tribler.community.anontunnel.globals import CIRCUIT_STATE_BROKEN, CIRCUIT_STATE_EXTENDING, CIRCUIT_STATE_READY
from Tribler.dispersy.candidate import CANDIDATE_WALK_LIFETIME, Candidate

__author__ = 'Chris'

from time import time

class Circuit:
    """ Circuit data structure storing the id, status, first hop and all hops """

    def __init__(self, circuit_id, goal_hops=0, candidate=None):
        """
        Instantiate a new Circuit data structure

        :param circuit_id: the id of the candidate circuit
        :param candidate: the first hop of the circuit
        :return: Circuit
        """

        self.circuit_id = circuit_id
        self.candidate = candidate
        self.hops = []
        self.goal_hops = goal_hops

        self.extend_strategy = None
        self.timestamp = None
        self.times = []
        self.bytes_up_list = []
        self.bytes_down_list = []

        self.bytes_down = [0, 0]
        self.bytes_up = [0, 0]

        self.speed_up = 0.0
        self.speed_down = 0.0
        self.last_incomming = time()

        self.unverified_hop = None
        """ :type : Hop """


    @property
    def bytes_downloaded(self):
        return self.bytes_down[1]

    @property
    def bytes_uploaded(self):
        return self.bytes_up[1]

    @property
    def online(self):
        return self.goal_hops == len(self.hops)

    @property
    def state(self):
        if self.hops == None:
            return CIRCUIT_STATE_BROKEN

        if len(self.hops) < self.goal_hops:
            return CIRCUIT_STATE_EXTENDING
        else:
            return CIRCUIT_STATE_READY

    @property
    def ping_time_remaining(self):
        too_old = time() - CANDIDATE_WALK_LIFETIME - 5.0
        diff = self.last_incomming - too_old
        return diff if diff > 0 else 0

    def __contains__(self, other):
        if isinstance(other, Candidate):
            # TODO: should compare to a list here
            return other == self.candidate

