__version__ = '1.0'
from kivy.app import App
from kivy.uix.screenmanager import ScreenManager, Screen
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.widget import Widget
from kivy.core.window import Window
from kivy.lang import Builder
from kivy.uix.button import Button
from kivy.core.image import Image as CoreImage
from kivy.graphics.texture import Texture
from kivy.clock import Clock
from kivy.properties import StringProperty, ObjectProperty


from kivy.uix.anchorlayout import AnchorLayout
from kivy.properties import ObjectProperty, ListProperty, BooleanProperty, \
    NumericProperty

import numpy
import android
import os
import fnmatch
from nfc import CreateNfcBeamUrisCallback
import io
import time
import threading
import functools

from cam import PreviewCallback, SurfaceHolderCallback, AndroidWidgetHolder, AndroidCamera

from jnius import autoclass, cast, detach
from jnius import JavaClass
from jnius import PythonJavaClass
from android.runnable import run_on_ui_thread
from android.runnable import Runnable

Context = autoclass('android.content.Context')
PythonActivity = autoclass('org.renpy.android.PythonActivity')
activity = PythonActivity.mActivity
Intent = autoclass('android.content.Intent')
Environment = autoclass('android.os.Environment')
Uri = autoclass('android.net.Uri')
NfcAdapter = autoclass('android.nfc.NfcAdapter')
File = autoclass('java.io.File')
CreateNfcBeamUrisCallback = autoclass('org.test.CreateNfcBeamUrisCallback')
MediaStore = autoclass('android.provider.MediaStore')
ThumbnailUtils = autoclass('android.media.ThumbnailUtils')
ImageView = autoclass('android.widget.ImageView')

MediaRecorder = autoclass('android.media.MediaRecorder')
Camera = autoclass('android.hardware.Camera')
CamCorderProfile = autoclass('android.media.CamcorderProfile')

Builder.load_file('main.kv')

thumbnail_sem = threading.BoundedSemaphore()
nfc_video_set = []


class HomeScreen(Screen):
	#Simple test function
	def AndroidTest(self):
		vibrator = activity.getSystemService(Context.VIBRATOR_SERVICE)
		if 'ANDROID_ROOT' in os.environ:
			vibrator.vibrate(3000)

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
	def getStoredMedia(self):
		DCIMdir = Environment.getExternalStoragePublicDirectory(Environment.DIRECTORY_DCIM)
		print DCIMdir.toURI().getPath()	
		self.ids.fileList.clear_widgets()
		for root, dirnames, filenames in os.walk(DCIMdir.getAbsolutePath()):
			for filename in fnmatch.filter(filenames,'*.mp4'):
				wid = FileWidget()
				wid.setName(filename)
				wid.setUri(root+'/'+filename)
				#Making thumbnails is ungodly slow, so it's threaded
				threading.Thread(target=wid.makeThumbnail).start()
				self.ids.fileList.add_widget(wid)

class FileWidget(BoxLayout):
	name = 'NO FILENAME SET'
	uri = None
	texture = None
	benchmark = time.time()
	lImageView = ImageView

	#Enumerator as per android.media.ThumbnailUtils
	MINI_KIND = 1 
	FULL_KIND = 2
	MICRO_KIND = 3

	def setName(self, nom):
		self.name = nom
		self.ids.filebutton.text = nom

	def setUri(self,ur):
		self.uri = ur

	#Called when pressed on the big filewidget button
	def pressed(self):
		print self.uri
		print 'Pressed'
		print nfc_video_set

	#Adds and removes the video files to the nfc set so that they can be transferred
	def toggle_nfc(self, state):
		print 'toggling', self.ids.nfc_toggler
		if(state == 'normal'):
			print 'button state up'
			nfc_video_set.remove(self.uri)
		if(state == 'down'):
			print 'button state down'
			nfc_video_set.append(self.uri)

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
		thumbnail_sem.acquire()
		thumbnail = ThumbnailUtils.createVideoThumbnail(self.uri,self.MINI_KIND)
		thumbnail_sem.release()
		Clock.schedule_once(functools.partial(self.displayAndroidThumbnail, thumbnail))
		pixels = [0] *thumbnail.getWidth() * thumbnail.getHeight()
		thumbnail.getPixels(pixels, 0,thumbnail.getWidth(),0,0,thumbnail.getWidth(), thumbnail.getHeight())
		#pixels = self.switchFormats(pixels)
		#Schedule the main thread to update the thumbnail's texture
	
		#Clock.schedule_once(functools.partial(self.displayThumbnail,thumbnail.getWidth(), thumbnail.getHeight(),pixels))
		print "Detatching thread"
		detach()

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
		img_view = ImageView(cast(Context, activity))
		print 'created view'
		img_view.setImageBitmap(bmp)
		self.ids.android.view = img_view
		
	#Benchmark function to help discover which function is slow	
	def bench(self):
		print "BENCHMARK: ", time.time() - self.benchmark
		self.benchmark = time.time()

class SearchScreen(Screen):
	def on_txt_input(self):
		Clock.unschedule(self.delayedSearch, all=True)
		if(self.ids.searchfield.text == ''):
			self.ids.fileList.clear_widgets()
		else:
			Clock.schedule_once(self.delayedSearch, 0.5)
	def delayedSearch(self, dt):
		print "TextSearch"
		wid = FileWidget()
		wid.setName(self.ids.searchfield.text)
		self.ids.fileList.clear_widgets()
		self.ids.fileList.add_widget(wid)

class CameraWidget(AnchorLayout):
    camera_size = ListProperty([320, 240])

    def __init__(self, **kwargs):
        super(CameraWidget, self).__init__(**kwargs)
        self._camera = AndroidCamera(size=self.camera_size, size_hint=(None, None))
	print 'HOERA!!!'
        self.add_widget(self._camera)

    def start(self):
        self._camera.start()

    def stop(self):
        self._camera.stop()

class CamScreen(Screen):
	pass

#class createCam():
#	cam = Camera.open()
#	Camera.setPreviewDisplay()
#	Camera.startPreview()
#
#	def prepareCamera(self):
#		self.camera = getCameraInstance()
#		self.mediaRecorder = MediaRecorder()
#
#		self.camera.unlock()
#		self.mediaRecorder.setCamera(self.camera)
#
#		self.mediaRecorder.setAudioSource(MediaRecorder.AudioSource.CAMCORDER)
#		self.mediaRecorder.setVideoSource(MediaRecorder.VideoSource.CAMERA)
#
#		self.mediaRecorder.setProfile(CamcorderProfile.get(CamcorderProfile.QUALITY_HIGH))
#
#		self.mediaRecorder.setOutputFile(getOutputMediaFile(MEDIA_TYPE_VIDEO).toString())
#
#		self.mediaRecorder.setPreviewDisplay(mPreview.getHolder().getSurface())


class Skelly(App):
	sm = ScreenManager()
	history = []
	HomeScr = HomeScreen(name='home')
	SearchScr = SearchScreen(name='search')
	CamScr = CamScreen(name='cam')
	sm.switch_to(HomeScr)

	#Method that request the device's NFC adapter and adds a Callback function to it to activate on an Android Beam Intent.
	def nfc_init(self):
		#Request the Activity to obtain the NFC Adapter and later add it to the Callback. 
		self.j_context = context = activity
		self.adapter = NfcAdapter.getDefaultAdapter(context)

		#Only activate the NFC functionality if the device supports it.
		if self.adapter is not None:
			self.callback = CreateNfcBeamUrisCallback()
			self.callback.addContext(context)
			self.adapter.setBeamPushUrisCallback(self.callback, context)

	def build(self):
		#Android back mapping
		android.map_key(android.KEYCODE_BACK,1001)
		win = Window
		win.bind(on_keyboard=self.key_handler)


		self.HomeScr.getStoredMedia()
		#Initialize NFC
		self.nfc_init()

		return self.sm

	#Function that helps properly implement the history function.
	#use this instead of switch_to
	def swap_to(self, Screen):
		self.history.append(self.sm.current_screen)
		self.sm.switch_to(Screen, direction='left')

	#required function by android, called when paused for multitasking
	def on_pause(self):
		return True

	#required function by android, called when asked to stop
	def on_stop(self):
		pass

	#Required function by android, called when resumed from a pause	
	def on_resume(self):
		#forces a refresh of the entire video list
		self.HomeScr.getStoredMedia()

	#Button handler function
	#also implements history function in tandem with swap_to()
	def key_handler(self,window,keycode1, keycode2, text, modifiers):
		if keycode1 in [27,1001]:
			if len(self.history ) != 0:
				print self.history
				self.sm.switch_to(self.history.pop(), direction = 'right')				
			else:
				App.get_running_app().stop()

if __name__== '__main__':
	Skelly().run()
