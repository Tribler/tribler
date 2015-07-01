__version__ = '1.0'
from kivy.app import App
from kivy.uix.relativelayout import RelativeLayout
from kivy.uix.stacklayout import StackLayout
from kivy.uix.widget import Widget
from kivy.uix.button import Button
from kivy.core.image import Image
from kivy.graphics.texture import Texture
from kivy.clock import Clock
from kivy.animation import Animation
from kivy.logger import Logger
from kivy.clipboard import Clipboard
from kivy.properties import ObjectProperty
from kivy.metrics import Metrics

import numpy
import os
import time
import threading
import functools

import globalvars

from Tribler.Core.TorrentDef import TorrentDef
from Tribler.Core.DownloadConfig import DownloadStartupConfig

from videoplayer import open_player

from jnius import autoclass, cast
from android.runnable import run_on_ui_thread
import android

Context = autoclass('android.content.Context')
PythonActivity = autoclass('org.renpy.android.PythonActivity')
activity = PythonActivity.mActivity
Uri = autoclass('android.net.Uri')
MediaStore = autoclass('android.provider.MediaStore')
ThumbnailUtils = autoclass('android.media.ThumbnailUtils')
ImageView = autoclass('android.widget.ImageView')
CompressFormat = autoclass('android/graphics/Bitmap$CompressFormat')
FileOutputStream = autoclass('java.io.FileOutputStream')
File = autoclass('java.io.File')

class FileWidget(RelativeLayout):
	name = "No Name Set"
	uri = "/pls/set/uri"
	texture = None
	benchmark = time.time()
	lImageView = ImageView
	thumbnail = None
	tdef = None
	creating = False

	# Enumerator as per android.media.ThumbnailUtils
	MINI_KIND = 1
	FULL_KIND = 2
	MICRO_KIND = 3
	# Enumerator as per Bitmap.CompressFormat
	JPEG = 1
	PNG = 2
	WEBP = 3

	def __init__(self, torrentname=None, uri=None, **kwargs):
		RelativeLayout.__init__(self, **kwargs)
		if torrentname is not None:
			self.setName(torrentname)
		if uri is not None:
			self.setUri(uri)
		if not self._check_torrent_made() and globalvars.triblerfun:
			threading.Thread(target=self._create_torrent).start()
			#for f in torrents:
			#	globalvars.scanner.addScanFile(f)
			#globalvars.scanner.scanFiles()

	def setName(self, nom):
		assert nom is not None
		self.name = nom
		self.ids.namelabel.text = nom

	def setUri(self, ur):
		assert ur is not None
		self.uri = ur
		strSplit = self.uri.split('/')
		strSplit.reverse()
		self.torUri = globalvars.torrentFolder.getAbsolutePath() + '/' + strSplit[0]

	def get_playtime(self):
		return None

	#Called when pressed on the big filewidget button
	def pressed(self):
		open_player(self.uri)

	def toggle_nfc(self, state):
		"""Adds and removes the video files to the nfc set so
		that they can be transferred
		"""
		if globalvars.nfcCallback is not None:
			Logger.info("Toggle NFC")
			if(state == 'normal'):
				print 'button state up'
				globalvars.nfcCallback.removeUris(self.uri)
				if self._check_torrent_made():
					globalvars.nfcCallback.removeUris(self.uri + ".torrent")

			if(state == 'down'):
				print 'button state down'
				globalvars.nfcCallback.addUris(self.uri)
				if self._check_torrent_made():
					globalvars.nfcCallback.addUris(self.uri + ".torrent")

		else:
			#Add method to throw a popup explaining that the feature is unavailable.
			pass

	def toggle_seed(self, state):
		"""Start and stop seeding with Tribler"""
		Logger.info("Toggle seeding")
		if globalvars.triblerfun and self._check_torrent_made():
			if state == 'normal':
				self._start_tribler()
			elif state == 'down':
				self._stop_tribler()

	#Android's Bitmaps are in ARGB format, while kivy expects RGBA.
	#This function swaps the bytes to their appropriate locations
	#It's super slow, and another method should be considered
	def switchFormats(self, pixels):
		bit = numpy.asarray([b for pixel in [((p & 0xFF0000) >> 16, (p & 0xFF00) >> 8, p & 0xFF, (p & 0xFF000000) >> 24) for p in pixels] for b in pixel],dtype=numpy.uint8)
		return bit

	#Function designed with multithreading in mind.
	#Generates the appropriate pixel data for use with the Thumbnails
	def makeThumbnail(self):
		#Android crashes when multiple threads call createVideoThumbnail, so we block access to it.
		#Luckily requesting thumbnails is pretty quick
		globalvars.thumbnail_sem.acquire()
		self.thumbnail = ThumbnailUtils.createVideoThumbnail(self.uri,self.MINI_KIND)
		#self.displayAndroidThumbnail(self.thumbnail)
		#Clock.schedule_once(functools.partial(self.displayAndroidThumbnail, self.thumbnail))
		globalvars.thumbnail_sem.release()
		pixels = [0] *self.thumbnail.getWidth() * self.thumbnail.getHeight()
		self.thumbnail.getPixels(pixels, 0,self.thumbnail.getWidth(),0,0,self.thumbnail.getWidth(), self.thumbnail.getHeight())
		pixels = self.switchFormats(pixels)
		#Schedule the main thread to update the thumbnail's texture

		Clock.schedule_once(functools.partial(self.displayThumbnail,self.thumbnail.getWidth(), self.thumbnail.getHeight(),pixels))
		print "Detatching thread"
		#detach()

	#New updated variant of Thumbnail creation. Generates and saves thumbnails to local storage
	#If file already exists or after generation, it will load the thumbnail
	def makeFileThumbnail(self):
		path = activity.getFilesDir().toURI().getPath()+'THUMBS/'
		if not os.path.exists(path):
			os.makedirs(path)
		path = path+self.name+'.jpg'
		if os.path.exists(path):
			print 'Thumbnail ', path, 'exists'
			Clock.schedule_once(functools.partial(self.loadFileThumbnail, path))
		else:
			print 'Thumbnail ',path, ' does not exist'
			thumb = ThumbnailUtils.createVideoThumbnail(self.uri,self.MINI_KIND)
			print path
			output = FileOutputStream(path, False)
			thumb.compress(CompressFormat.valueOf('JPEG'), 80,output)
			output.close()
			Clock.schedule_once(functools.partial(self.loadFileThumbnail, path))

	#Loads the thumbnail from a given path and sets it in the FileWidget
	def loadFileThumbnail(self, path, *largs):
		print 'Attempting to set Image: ', path
		self.ids.img.source = path
		print self.ids.img.source

	#Function called by makeThumbnail to set the thumbnail properly
	#Displaying a new texture does not work on a seperate thread, so the main thread had to handle it
	def displayThumbnail(self, width, height, pixels, *largs):
		tex = Texture.create(size=(width,height) , colorfmt= 'rgba', bufferfmt='ubyte')
		tex.blit_buffer(pixels, colorfmt = 'rgba', bufferfmt = 'ubyte')
		tex.flip_vertical()
		self.texture = tex
		print self.texture
		self.ids.img.texture = self.texture
		self.ids.img.canvas.ask_update()

	#Function called by makeThumbnail to set the thumbnail through android's widget
	#So no conversion is needed
	@run_on_ui_thread
	def displayAndroidThumbnail(self, bmp, *largs):
		print 'display'
		print self.thumbnail
		img_view = ImageView(cast(Context, activity))
		print 'created view'
		img_view.setImageBitmap(self.thumbnail)
		self.ids.android.view = img_view
		print "sem released"

	#Benchmark function to help discover which function is slow
	def bench(self):
		print "BENCHMARK: ", time.time() - self.benchmark
		self.benchmark = time.time()

	#Deletes file and thumbnail associated with this widget
	def delete(self):
		anim = Animation(opacity=0, height=0, duration = 0.5)
		anim.start(self)
		Clock.schedule_once(self._remove,0.5)

	def _remove(self, _):
		"""Removes this widget from the list with a transition effect
		In addition, remove the video and associated files, stop seeding
		"""
		self._delete_torrent()
		self.parent.remove_widget(self)
		os.remove(self.uri)
		os.remove(self.ids.img.source)

	def share_magnet_link(self):
		if self._check_torrent_made() and globalvars.triblerfun:
			sess = globalvars.skelly.tw.get_session_mgr().get_session()
			magnet = sess.get_download(self.tdef.infohash).get_magnet_link()
			if magnet is not None:
				android.action_send('text/plain', text=magnet)
		else:
			# Show error that magnet is not yet ready?
			pass

	def _check_torrent_made(self):
		""" Check if a .torrent exists for this file and if it does, import
		Return boolean result
		"""
		if os.path.isfile(self.torUri + ".torrent"):
			Logger.info("Found torrent: " + self.torUri + ".torrent")
			self.tdef = TorrentDef.load(self.torUri + ".torrent")
			return True
		return False

	def _create_torrent(self):
		"""Create tdef, save .torrent"""
		assert globalvars.triblerfun
		if self._check_torrent_made() is False:
			Logger.info("Creating TDEF for: ", self.name)
			self.tdef = TorrentDef()
			self.tdef.add_content(self.uri, playtime=self.get_playtime())
			self.tdef.set_dht_nodes([["router.bittorrent.com", 8991]])
			self.tdef.finalize()
			self.tdef.save(self.torUri + ".torrent")
			self._check_torrent_made()
		else:
			Logger.info("Torrent already created for: " + self.name)

	def _delete_torrent(self):
		""" Delete .torrent,tdef to None and remove download from Tribler"""
		if self._check_torrent_made() and globalvars.triblerfun:
			self._stop_tribler()
			os.remove(self.torUri + ".torrent")
			self.tdef = None
			#self.files.append

	def _stop_tribler(self):
		"""Stop downloading with tribler"""
		assert self.tdef is not None and self.tdef.is_finalized()
		assert globalvars.triblerfun
		sess = globalvars.skelly.tw.get_session_mgr().get_session()
		if sess.has_download(self.tdef.infohash):
			sess.remove_download_by_id(self.tdef.infohash)
			Logger.info("Download removed from Tribler: " + self.tdef.get_name())

	def _start_tribler(self):
		""" Start download with Tribler. Seeds when file already exists
		Returns the Download handler
		"""
		assert self.tdef is not None and self.tdef.is_finalized()
		assert globalvars.triblerfun
		sess = globalvars.skelly.tw.get_session_mgr().get_session()
		if not sess.has_download(self.tdef.infohash):
			Logger.info("Adding torrent to tribler: " + self.tdef.get_name())
			dscfg = DownloadStartupConfig()
			dscfg.set_dest_dir(os.path.dirname(self.uri))
			return sess.start_download(self.tdef, dscfg)
		else:
			Logger.info("Already added to Tribler: " + self.tdef.get_name())
			d = sess.get_download(self.tdef.infohash)
			d.force_recheck()
			return d

	def openMenu(self, target):
		FileTripleDot(target, self)

class FileTripleDot(RelativeLayout):
	target = ObjectProperty(None)
	owner = ObjectProperty(None)
	#self.opacity = 0;
	def __init__(self, tar = None, owner = None, **kwargs):
		RelativeLayout.__init__(self, **kwargs)
		if(tar is not None):
			self.target = tar
		if self.target is not None:
			self.target.add_widget(self)
			print "Menu added?"
		if owner is not None:
			self.owner = owner
		self.pos = self.owner.to_window(self.owner.x, self.owner.y)
		self.y = self.y + self.owner.height - self.ids.buttons.height
		if self.y  < 0:
			print 'too low'
			self.y = 0
		if self.y+self.ids.buttons.height+self.ids.container.padding[1]+self.ids.container.padding[3] > self.target.height:
			print 'too high', self.y+self.ids.buttons.height, self.target.height
			self.y = self.target.height - self.ids.buttons.height - self.ids.container.padding[1]-self.ids.container.padding[3]
	def close(self):
		self.target.remove_widget(self)
