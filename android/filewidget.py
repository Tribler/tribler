__version__ = '1.0'
from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.widget import Widget
from kivy.uix.button import Button
from kivy.core.image import Image
from kivy.graphics.texture import Texture
from kivy.clock import Clock
from kivy.animation import Animation


from kivy.uix.anchorlayout import AnchorLayout
from kivy.properties import ObjectProperty

import numpy
import android
import os
import io
import time
import threading
import functools

from Tribler.Core import TorrentDef

import globalvars

from jnius import autoclass, cast, detach
from jnius import JavaClass
from jnius import PythonJavaClass
from android.runnable import run_on_ui_thread


Context = autoclass('android.content.Context')
PythonActivity = autoclass('org.renpy.android.PythonActivity')
activity = PythonActivity.mActivity
Uri = autoclass('android.net.Uri')
MediaStore = autoclass('android.provider.MediaStore')
ThumbnailUtils = autoclass('android.media.ThumbnailUtils')
ImageView = autoclass('android.widget.ImageView')
CompressFormat = autoclass('android/graphics/Bitmap$CompressFormat')
FileOutputStream = autoclass('java.io.FileOutputStream')

class FileWidget(BoxLayout):
	name = 'NO FILENAME SET'
	uri = None
	texture = None
	benchmark = time.time()
	lImageView = ImageView
	thumbnail = None
	tdef = None

	#Enumerator as per android.media.ThumbnailUtils
	MINI_KIND = 1
	FULL_KIND = 2
	MICRO_KIND = 3
	#Enumerator as per Bitmap.CompressFormat
	JPEG = 1
	PNG = 2
	WEBP = 3

	def __init__(self):
		#TODO: Load tdef if it exists and if it does, change icon to upload

	def setName(self, nom):
		self.name = nom
		self.ids.filebutton.text = nom

	def setUri(self,ur):
		self.uri = ur

	def get_playtime(self):
		return None

	#Called when pressed on the big filewidget button
	def pressed(self):
		print self.uri
		print 'Pressed'

	#Adds and removes the video files to the nfc set so that they can be transferred
	def toggle_nfc(self, state):

		print 'toggling', self.ids.nfc_toggler
		if(state == 'normal'):
			print 'button state up'
			globalvars.nfcCallback.removeUris(self.uri)

		if(state == 'down'):
			print 'button state down'
			globalvars.nfcCallback.addUris(self.uri)


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
		Clock.schedule_once(self.remove,0.5)
	#Removes this widget from the list with a transition effect
	def remove(self, *largs):
		self.parent.remove_widget(self)
		os.remove(self.uri)
		os.remove(self.ids.img.source)

	# Create .torrent for this video
	def create_torrent(self):
		tdef = TorrentDef()
		tdef.add_content(self.uri, playtime = self.get_playtime())
		fin_thread = threading.Thread(target=TorrentDef.TorrentDef.finalize,name="Finalize Torrent Thread",args=tdef, kwargs={userprogresscallback = self._torrent_finalize_callback})

	# Seed torrent using Tribler
	def seed_torrent(self):
		print("TODO: Add torrent to Tribler")
		if(globalvars.skelly.tw.keep_running()):
			print("Triber running")

	def _torrent_finalize_callback(self, fraction):
		print("Fraction done: " + fraction)
