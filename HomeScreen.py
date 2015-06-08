from kivy.uix.screenmanager import Screen

from kivy.uix.anchorlayout import AnchorLayout
from kivy.properties import ObjectProperty, ListProperty
from kivy.uix.boxlayout import BoxLayout
from kivy.animation import Animation
from kivy.clock import Clock


import fnmatch
import io
import functools
import Queue
import threading
import os

from jnius import autoclass, cast, detach
from jnius import JavaClass
from jnius import PythonJavaClass

from camtest import CamTestCamera

from android.runnable import run_on_ui_thread

import globalvars
from FileWidget import FileWidget


Context = autoclass('android.content.Context')
PythonActivity = autoclass('org.renpy.android.PythonActivity')
activity = PythonActivity.mActivity
Intent = autoclass('android.content.Intent')
Environment = autoclass('android.os.Environment')
Uri = autoclass('android.net.Uri')
File = autoclass('java.io.File')
MediaStore = autoclass('android.provider.MediaStore')
Camera = autoclass('android.hardware.Camera')






class HomeScreen(Screen):
	discovered_media = []
	non_thumbnailed = Queue.Queue()
	thumbnail_thread = None
	wid_sem = threading.BoundedSemaphore()
	Finished = object()
	def __init__(self, **kwargs):
		self.thumbnail_thread = threading.Thread(target=self.loadThumbnails)
		self.thumbnail_thread.start()
		super(Screen,self).__init__(**kwargs)
	#Simple test function
	def AndroidTest(self):
		vibrator = activity.getSystemService(Context.VIBRATOR_SERVICE)
		if 'ANDROID_ROOT' in os.environ:
			vibrator.vibrate(3000)
		print self.discovered_media
		print activity.getFilesDir().getAbsolutePath()
		#for root, dirnames, filenames in os.walk('./'):
		#	print root,'/',filenames
		print Window.size

	#Function for starting the camera application
	def startCamera(self):
		intention = Intent(MediaStore.INTENT_ACTION_VIDEO_CAMERA)
		#When java requires a "Context" usually in the shape of "this",
		#it has to be casted from our activity
		self.con = cast(Context, activity)			
		intention.resolveActivity(self.con.getPackageManager())	
		if intention.resolveActivity(self.con.getPackageManager()) != None:
			#Called with 1 as parameter so the application waits
			#until the camera returns it's video			
			activity.startActivityForResult(intention,1)

	#Test function for adding a number of fake video buttons
	def addVideo(self):
		wid = FileWidget()
		wid.setName('FakeVid!')
		self.ids.fileList.add_widget(wid)

	#Useful support function to print the location of the DCIM dir
	def printDir(self):	
		DCIMdir = Environment.getExternalStoragePublicDirectory(Environment.DIRECTORY_DCIM)
		print DCIMdir.list()

	#Traverse DCIM folder for video files, and create a listing out of the discovered files
	#Automatically generates Filewidgets and adds them to the Scrollview
	@run_on_ui_thread
	def getStoredMedia(self):
		if  globalvars.nfcCallback is not None:
			globalvars.nfcCallback.clearUris()
		files = []
		DCIMdir = Environment.getExternalStoragePublicDirectory(Environment.DIRECTORY_DCIM)
		print DCIMdir.toURI().getPath()	
		self.ids.fileList.clear_widgets()
		for root, dirnames, filenames in os.walk(DCIMdir.getAbsolutePath()):
			for filename in fnmatch.filter(filenames,'*.mp4'):
				#wid = FileWidget()
				#wid.setName(filename)
				#wid.setUri(root+'/'+filename)
				##Making thumbnails is ungodly slow, so it's threaded
				#threading.Thread(target=wid.makeThumbnail).start()
				#self.ids.fileList.add_widget(wid)
				files.append( (filename, root+'/'+filename) )
		self.discovered_media = files
		
		Clock.schedule_once(functools.partial(self.createFileWidgets,self.discovered_media))
				
	def createFileWidget(self, tup, *largs):
		filename, uri = tup	
		wid = FileWidget()
		wid.setName(filename)
		wid.setUri(uri)
		self.ids.fileList.add_widget(wid)
		#self.wid_sem.acquire()
		self.non_thumbnailed.put(wid)
		#if(self.thumbnail_thread.isAlive() == False) :
		#	self.thumbnail_thread.start()

	def createFileWidgets(self,media, *largs):
		for i in range(0,10):
			if( len(media) != 0):			
				tup = media.pop(0)		
				self.createFileWidget(tup)
				Clock.schedule_once(functools.partial(self.createFileWidgets, media))
			else: break		

	def loadThumbnails(self):
		while True:
			print 'Thump', globalvars.app_ending
			#self.wid_sem.acquire()
			wid = self.non_thumbnailed.get()
			if(wid is self.Finished):
				print "Ending Thumbnail Thread"
				detach()
				break
			print 'IMAGE TIME'
			print wid.uri
			wid.makeFileThumbnail()
		detach()
	def endThumbnailThread(self):
		self.non_thumbnailed.queue.clear()
		self.non_thumbnailed.put(self.Finished)
	def openGearMenu(self):
		gearMenu = GearMenu()
		gearMenu.setScreen(self)
		gearMenu.opacity = 0
		anim = Animation(opacity = 1,duration=0.2)
		self.ids.layer.add_widget(gearMenu)
		anim.start(gearMenu)

	def closeGearMenu(self):
		self.ids.layer.remove_widget(GearMenu)

class GearMenu(BoxLayout):
	screen = ObjectProperty(None)
	def setScreen(self, scr):
		self.screen = scr
	pass
