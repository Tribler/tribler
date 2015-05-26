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

import numpy
import array
import android
import os
#from nfc import CreateNfcBeamUrisCallback
#from nfc2 import CreateNfcMessageCallback
import fnmatch
from nfc import CreateNfcBeamUrisCallback
import io
import time
import threading
import functools


from jnius import autoclass, cast, detach
from jnius import JavaClass
from jnius import PythonJavaClass
from android.runnable import run_on_ui_thread
from android.runnable import Runnable

mContext = autoclass('android.content.Context')
PythonActivity = autoclass('org.renpy.android.PythonActivity')
activity = PythonActivity.mActivity
Intent = autoclass('android.content.Intent')
mEnvironment = autoclass('android.os.Environment')
Uri = autoclass('android.net.Uri')
Builder.load_file('main.kv')

NfcAdapter = autoclass('android.nfc.NfcAdapter')
IntentFilter = autoclass('android.content.IntentFilter')
PendingIntent = autoclass('android.app.PendingIntent')

NdefMessage = autoclass('android.nfc.NdefMessage')
NdefRecord = autoclass('android.nfc.NdefRecord')
String = autoclass('java.lang.String')
File = autoclass('java.io.File')
CreateNfcBeamUrisCallback = autoclass('org.test.CreateNfcBeamUrisCallback')

thumbnail_sem = threading.BoundedSemaphore()
nfc_video_set = []



class HomeScreen(Screen):

	mMediaStore = autoclass('android.provider.MediaStore')
	mFile = autoclass('java.io.File')

	def likeMore(self):
		self.ids.button1.text = self.ids.button1.text+"!"
	def AndroidTest(self):
		vibrator = activity.getSystemService(mContext.VIBRATOR_SERVICE)
		if 'ANDROID_ROOT' in os.environ:
			vibrator.vibrate(3000)	
		else:
			print 'not android?'
			print os.environ
	
	def startCamera(self):

		#intention = Intent(self.mMediaStore.ACTION_VIDEO_CAPTURE)
		intention = Intent(self.mMediaStore.INTENT_ACTION_VIDEO_CAMERA)
		self.con = cast(mContext, activity)			
		intention.resolveActivity(self.con.getPackageManager())	
		if intention.resolveActivity(self.con.getPackageManager()) != None:
			activity.startActivityForResult(intention,1)
	ButtonNumber = 0
	def addVideo(self):
		wid = FileWidget()
		wid.setName('Name %d' % self.ButtonNumber)
		self.ButtonNumber = self.ButtonNumber+1
		self.ids.fileList.add_widget(wid)


	def printDir(self):	
		DCIMdir = mEnvironment.getExternalStoragePublicDirectory(mEnvironment.DIRECTORY_DCIM)
		print DCIMdir.list()
	
	def getStoredMedia(self):
		global files
		DCIMdir = mEnvironment.getExternalStoragePublicDirectory(mEnvironment.DIRECTORY_DCIM)
		print DCIMdir.toURI().getPath()	
		self.ids.fileList.clear_widgets()
		for root, dirnames, filenames in os.walk(DCIMdir.getAbsolutePath()):
			for filename in fnmatch.filter(filenames,'*.mp4'):
				wid = FileWidget()
				wid.setName(filename)
				wid.setUri(root+'/'+filename)
				if(wid.uri in nfc_video_set):
					wid.ids.button_layout.nfc_toggle.state = 'down'
				threading.Thread(target=wid.makeThumbnail).start()
				self.ids.fileList.add_widget(wid)
				

class CameraScreen(Screen):
	mMediaStore = autoclass('android.provider.MediaStore')
	def startCamera(self):

		intention = Intent(self.mMediaStore.ACTION_VIDEO_CAPTURE)
		self.con = cast(mContext, activity)			
		intention.resolveActivity(self.con.getPackageManager())	
		if intention.resolveActivity( self.con.getPackageManager()) != None:
			activity.startActivityForResult(intention,1)

class NfcScreen(Screen):
	def printDir(self):	
		DCIMdir = mEnvironment.getExternalStoragePublicDirectory(mEnvironment.DIRECTORY_DCIM)
		print DCIMdir.list()


class FileWidget(BoxLayout):

	mBitmap = autoclass("android.graphics.Bitmap")
	mCompressFormat = autoclass("android.graphics.Bitmap$CompressFormat")
	mByteArrayOutputStream = autoclass ("java.io.ByteArrayOutputStream")
	mArrays = autoclass("java.util.Arrays")
	mColor = autoclass("android.graphics.Color")
	mThumbnailUtils = autoclass ("android.media.ThumbnailUtils")

	#mThumbnails = autoclass("android.provider.MediaStore.Video.Thumbnails")
	name = 'NO FILENAME SET'
	uri = None
	texture = None
	#thumbnail = None  #Gotta make a default for this later
	MICRO_KIND = 3
	FULL_KIND = 2
	MINI_KIND = 1
	def setName(self, nom):
		self.name = nom
		self.ids.filebutton.text = nom
	def setUri(self,ur):
		self.uri = ur
	def setThumb(self,thumb):
		self.thumbnail = thumb
	def pressed(self):
		print self.uri
		
		#threading.Thread(target=self.makeThumbnail).start()
		#Runnable(self.makeThumbnail)()
		print 'Pressed'
		print nfc_video_set
	def toggle_nfc(self, state):
		print 'toggling', self.ids.nfc_toggler
		if(state == 'normal'):
			print 'button state up'
			nfc_video_set.remove(self.uri)
		if(state == 'down'):
			print 'button state down'
			nfc_video_set.append(self.uri)
		
	def switchFormats(self, pixels):
		print 'StartSwitch'
		bit = numpy.asarray([b for pixel in [((p & 0xFF0000) >> 16, (p & 0xFF00) >> 8, p & 0xFF, (p & 0xFF000000) >> 24) for p in pixels] for b in pixel],dtype=numpy.uint8)	
		return bit
	#@run_on_ui_thread
	def makeThumbnail(self):	
#		while True:
#			pass
		thumbnail_sem.acquire()
		thumbnail = self.mThumbnailUtils.createVideoThumbnail(self.uri,self.MINI_KIND)
		thumbnail_sem.release()
		#tex = Texture.create(size=(thumbnail.getWidth(),thumbnail.getHeight()) , colorfmt= 'rgba', bufferfmt='ubyte')
		pixels = [0] *thumbnail.getWidth() * thumbnail.getHeight()
		thumbnail.getPixels(pixels, 0,thumbnail.getWidth(),0,0,thumbnail.getWidth(), thumbnail.getHeight())
		pixels = self.switchFormats(pixels)	
		#tex.blit_buffer(pixels, colorfmt = 'rgba', bufferfmt = 'ubyte')
		#tex.flip_vertical()
		#self.texture = tex
		#print self.texture
		#self.ids.img.canvas.ask_update()
		Clock.schedule_once(functools.partial(self.displayThumbnail,thumbnail.getWidth(), thumbnail.getHeight(),pixels))
		print "Detatching thread"
		detach()
	def displayThumbnail(self, width, height, pixels, *largs):
		tex = Texture.create(size=(width,height) , colorfmt= 'rgba', bufferfmt='ubyte')
		#pixels = self.switchFormats(pix)
		tex.blit_buffer(pixels, colorfmt = 'rgba', bufferfmt = 'ubyte')
		tex.flip_vertical()
		self.texture = tex
		print self.texture
		self.ids.img.texture = self.texture
		self.ids.img.canvas.ask_update()
	
	benchmark = time.time()
	def bench(self):
		print "BENCHMARK: ", time.time() - self.benchmark
		self.benchmark = time.time()
				


class Skelly(App):
	sm = ScreenManager()
	history = []
	HomeScr = HomeScreen(name='home')
	NfcScr = NfcScreen(name='nfc')
	sm.switch_to(HomeScr)

	def nfc_init(self):
		self.j_context = context = activity
		self.currentApp = File((cast(mContext, context)).getPackageResourcePath())

		self.adapter = NfcAdapter.getDefaultAdapter(context)
#		self.pending_intent = PendingIntent.getActivity(context, 0, Intent(context, context.getClass()).addFlags(Intent.FLAG_ACTIVITY_SINGLE_TOP), 0)

#		self.ndef_detected = IntentFilter(NfcAdapter.ACTION_NDEF_DISCOVERED)
#		self.ndef_detected.addDataType('text/plain')
#		self.ndef_exchange_filters = [self.ndef_detected]

#		self.callback = CreateNfcBeamUrisCallback()
		if self.adapter is not None:
			self.callback = CreateNfcBeamUrisCallback()
			self.callback.addContext(context)
			self.adapter.setBeamPushUrisCallback(self.callback, context)

#		self.call = CreateNfcMessageCallback()
#		self.adapter.setNdefPushMessageCallback(self.call, context)

#		print self.adapter
#		print self.ndef_exchange_filters

	def on_new_intent(self, intent):
		print 'On New Intent: ', intent.getAction()

		if intent.getAction() != NfcAdapter.ACTION_NDEF_DISCOVERED:
			print 'Invalid Intent detected.'
			return

	def build(self):
		android.map_key(android.KEYCODE_BACK,1001)
		win = Window
		win.bind(on_keyboard=self.key_handler)


		self.HomeScr.getStoredMedia()
		self.nfc_init()

		return self.sm
	def swap_to(self, Screen):
		self.history.append(self.sm.current_screen)
		self.sm.switch_to(Screen, direction='left')

	def on_pause(self):
		return True
	def on_stop(self):
		pass
	def on_resume(self):
		self.HomeScr.getStoredMedia()
	def key_handler(self,window,keycode1, keycode2, text, modifiers):
		if keycode1 in [27,1001]:
			if len(self.history ) != 0:
				print self.history
				self.sm.switch_to(self.history.pop(), direction = 'right')				
			else:
				App.get_running_app().stop()

if __name__== '__main__':
	Skelly().run()
