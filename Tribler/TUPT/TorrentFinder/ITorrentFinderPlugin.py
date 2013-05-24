from yapsy.IPlugin import IPlugin

class ITorrentFinderPlugin(IPlugin):
	
	def GetTorrentDefsForMovie(self, movie):
		"""Receive a Movie object and return a list of matching IMovieTorrentDefs
		"""
		pass