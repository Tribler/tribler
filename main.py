__version__ = '1.0'
from kivy.app import App
from kivy.uix.screenmanager import ScreenManager, Screen
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.widget import Widget
from kivy.core.window import Window
from kivy.lang import Builder
from kivy.clock import Clock
from kivy.uix.anchorlayout import AnchorLayout
from kivy.properties import ObjectProperty, ListProperty

import android
import os
from nfc import CreateNfcBeamUrisCallback
import io
import threading

from HomeScreen import HomeScreen
from FileWidget import FileWidget
from camtest import CamTestCamera
import globalvars

from jnius import autoclass, cast, detach
from jnius import JavaClass
from jnius import PythonJavaClass
from android.runnable import run_on_ui_thread

Context = autoclass('android.content.Context')
PythonActivity = autoclass('org.renpy.android.PythonActivity')
activity = PythonActivity.mActivity
Intent = autoclass('android.content.Intent')
Uri = autoclass('android.net.Uri')
NfcAdapter = autoclass('android.nfc.NfcAdapter')
File = autoclass('java.io.File')
CreateNfcBeamUrisCallback = autoclass('org.test.CreateNfcBeamUrisCallback')
MediaStore = autoclass('android.provider.MediaStore')
MediaRecorder = autoclass('android.media.MediaRecorder')
Camera = autoclass('android.hardware.Camera')
CamCorderProfile = autoclass('android.media.CamcorderProfile')
TextUtils = autoclass('android.text.TextUtils')
MediaColumns = autoclass('android.provider.MediaStore$MediaColumns')

Builder.load_file('main.kv')

class SearchScreen(Screen):
	#Predefined kivy function that gets called every time the text in the inputfield changes
	#Calls delayedSearch if the last change was over 0.5 seconds ago
	def on_txt_input(self):
		Clock.unschedule(self.delayedSearch, all=True)
		if(self.ids.searchfield.text == ''):
			self.ids.fileList.clear_widgets()
		else:
			Clock.schedule_once(self.delayedSearch, 0.5)
	#Currently a filler function that gets called when a search is attempted
	#currently displays a filewidget with the contents of the search
	def delayedSearch(self, dt):
		print "TextSearch"
		wid = FileWidget()
		wid.setName(self.ids.searchfield.text)
		self.ids.fileList.clear_widgets()
		self.ids.fileList.add_widget(wid)


class CameraWidget(AnchorLayout):
	camera_size = ListProperty([800, 700])
#	camera_size = ListProperty([480, 360])
	passes = 0

	def __init__(self, **kwargs):
		super(CameraWidget, self).__init__(**kwargs)
##		self._camera = AndroidCamera(size=self.camera_size, size_hint=(None, None))
		self._camera = CamTestCamera(size=self.size, size_hint=(None, None))
#	        self.add_widget(self._camera)
		self.bind(size=self.update)
	def update(self, *args):
		print self.passes
		print self.size
		if self.passes == 2:
			print 'Camera Size Changed to', self.size
			width_ratio = (self.size[1] * (9./16.0) )  / self.size[0]
			print width_ratio
			self._camera = CamTestCamera(size=self.size, size_hint=(width_ratio, 1))
		        self.add_widget(self._camera)
			self.unbind(size=self.update)
		else:
			self.passes+=1

	def start(self):
		print 'Start camera'
		self._camera.start()

	def stop(self):
		print 'Stop camera'
		self._camera.stop()

class CamTestWidget(BoxLayout):

	def __init__(self, **kwargs):
		super(CamTestWidget, self).__init__(**kwargs)
		self.camera = CamTestCamera()
		self.add_widget(self.camera)

	def push(self):
		self.camera.pushButton()

class CamScreen(Screen):
	def on_enter(self):
		cam = self.ids.camera
		if cam._camera != None:
			cam.start()
	def on_leave(self):
		cam = self.ids.camera
		if cam._camera != None:
			cam.stop()
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
			#global nfcCallback
			globalvars.nfcCallback = CreateNfcBeamUrisCallback()
			globalvars.nfcCallback.addContext(context)
			self.adapter.setBeamPushUrisCallback(globalvars.nfcCallback, context)

	def handle_nfc_view(self, beamUri):
		if not TextUtils.equals(beamUri.getAuthority(), MediaStore.getAuthority()):
			print 'Wrong content provider for beamed file(s).'
		else:
			projection = MediaColumns.DATA
			pathCursor = Context.getContentResolver().query(beamUri, projection, None, None, None)

			if pathCursor is not None and pathCursor.movetoFirst():
				filenameIndex = pathCursor.getColumnIndex(MediaColumns.DATA)
				fileName = pathCursor.getString(filenameIndex)
				copiedFile = File(fileName)
				return copiedFile.getParentFile()
			else:
				return None

	def build(self):
		#Android back mapping
		android.map_key(android.KEYCODE_BACK,1001)
		win = Window
		win.bind(on_keyboard=self.key_handler)


		self.nfc_init()
		self.HomeScr.getStoredMedia()

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
		globalvars.app_ending = True
		print "Terminating Application NOW"
		self.HomeScr.endThumbnailThread()

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
