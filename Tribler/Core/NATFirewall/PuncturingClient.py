# Written by Lucia D'Acunto
# see LICENSE.txt for license information

import sys
from natcheck import *
import random
from thread import *
import socket
from Tribler.Core.simpledefs import *



class PuncturingClient:

	__single = None


    
	def __init__(self):
		if PuncturingClient.__single:
			raise RuntimeError, "PuncturingClient is singleton"
		PuncturingClient.__single = self

		self.session = None
		self.nat_type = "Unknown NAT/Firewall"



	def getInstance(*args, **kw):
		if PuncturingClient.__single is None:
			PuncturingClient(*args, **kw)
		return PuncturingClient.__single
	getInstance = staticmethod(getInstance)



	# Find out NAT type and public address and port
	def natcheck(self, udpsock, privateIP, privatePort, server1, server2):

		NatType, publicIP, publicPort = GetNATType(udpsock, privateIP, privatePort, server1, server2)
		dprint("NAT Type: " + NatType[1])
		dprint("Public Address: " + publicIP + ":" + str(publicPort))
		dprint("Private Address: " + privateIP + ":" + str(privatePort))

		return NatType, publicIP, publicPort, privateIP, privatePort



	# Register connection information
	def register(self, request, tcpsock):

		BUFSIZ = 1024

		reply = ""

		try:
			tcpsock.send(request)

		except error, (errno, strerror):

			dprint(strerror)
	
		tcpsock.settimeout(10)

		try:
			reply = tcpsock.recv(BUFSIZ)

		except timeout:

			dprint("Connection to the coordinator has timed out")

		except socket.error, (errno, strerror):

			dprint("Connection error with the coordinator: %s (%s)" % (strerror, str(errno)))

			if tcpsock:
				tcpsock.close()

		return reply



	def get_nat_type(self):
		return self.nat_type


	# Main method of the class: launches nat discovery algorithm
	def firewall_puncturing(self, sess):

		# Set up configuration
		self.session = sess

		privatePort = self.session.get_puncturing_private_port()
		servers = self.session.get_stun_servers()
		server1 = servers[0]
		server2 = servers[1]
		coordinators = self.session.get_puncturing_coordinators()
		coordinator = coordinators[0]

		dprint('Starting firewall puncturing client with %s %s %s %s' % (privatePort, server1, server2, coordinator))

		# Set up the sockets
		s = socket.socket()
		s.connect(('google.com',80))
		privateIP = s.getsockname()[0]
		del s

		privateAddr = (privateIP, privatePort)

		# TCP socket
		tcpsock = socket.socket(AF_INET, SOCK_STREAM)

		bind = 0

		while bind == 0:

			privateAddr = (privateIP, privatePort)
			dprint("binding address: " + str(privateAddr))
		            
			try:
				tcpsock.bind(privateAddr)
				bind = 1

			except socket.error, (errno, strerror):

				privatePort += 1
				bind = 0

				if tcpsock :
					tcpsock.close()
					tcpsock = False
					tcpsock = socket.socket(AF_INET, SOCK_STREAM)

				dprint("Could not open socket: %s" % (strerror))
		            
		tcpsock.settimeout(30)

		try:
			tcpsock.connect(coordinator)

		except timeout:

			if tcpsock:
				tcpsock.close()
				tcpsock = False

			dprint("Connection to the coordinator has timed out")

		except socket.error, (errno, strerror):

			if tcpsock:
				tcpsock.close()
				tcpsock = False
				
			dprint("Could not connect socket: %s" % (strerror))
	
		# UDP socket
		udpsock = socket.socket(AF_INET, SOCK_DGRAM)
		udpsock.setsockopt(SOL_SOCKET,SO_REUSEADDR,1)

		try:
			udpsock.bind(privateAddr)

		except socket.error, (errno, strerror):

			if udpsock:
				udpsock.close()
				udpsock = False

			dprint("Could not open socket: %s" % (strerror))
	
		if udpsock:
			udpsock.settimeout(5)

			# Check what kind of NAT the peer is behind
			NatType, publicIP, publicPort, privateIP, privatePort = self.natcheck(udpsock, privateIP, privatePort, server1, server2)

			self.nat_type = NatType[1]

			udpsock.close()

			if tcpsock:
				# Register on coordinator server
				request = "REGISTER(" + str(NatType[0]) + "," + publicIP + "," + publicPort + "," + privateIP + "," + str(privatePort) + ")"
				dprint(request)

				reply = self.register(request, tcpsock)
				dprint(reply)

				tcpsock.close()
