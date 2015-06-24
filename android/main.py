__version__ = '1.1'
from kivy.app import App
from kivy.uix.screenmanager import ScreenManager, Screen
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.widget import Widget
from kivy.core.window import Window
from kivy.lang import Builder
from kivy.clock import Clock
from kivy.uix.anchorlayout import AnchorLayout
from kivy.properties import ObjectProperty, ListProperty

from Tribler.Core.Utilities.twisted_thread import reactor, stop_reactor
from triblerwrapper.Environment import init_environment
init_environment()
from triblerwrapper.TriblerWrapper import TriblerWrapper

import android
import os
from nfc import CreateNfcBeamUrisCallback
import io
import threading
import time

from homescreen import HomeScreen
from torrentscreen import TorrentWidget, TorrentInfoScreen
from androidcamera import AndroidCamera
from homescreen import HomeScreen
import globalvars

from jnius import autoclass, cast, detach
from jnius import JavaClass
from jnius import PythonJavaClass
from android.runnable import run_on_ui_thread

from filescanner import FileScanner

Context = autoclass('android.content.Context')
PythonActivity = autoclass('org.renpy.android.PythonActivity')
activity = PythonActivity.mActivity
Intent = autoclass('android.content.Intent')
Uri = autoclass('android.net.Uri')
NfcAdapter = autoclass('android.nfc.NfcAdapter')
File = autoclass('java.io.File')
CreateNfcBeamUrisCallback = autoclass('org.tribler.CreateNfcBeamUrisCallback')
MediaStore = autoclass('android.provider.MediaStore')
MediaRecorder = autoclass('android.media.MediaRecorder')
Camera = autoclass('android.hardware.Camera')
CamCorderProfile = autoclass('android.media.CamcorderProfile')
TextUtils = autoclass('android.text.TextUtils')
MediaColumns = autoclass('android.provider.MediaStore$MediaColumns')
Environment = autoclass('android.os.Environment')
Builder.load_file('main.kv')

"""
The screen for searching for torrents using Dispersy.
"""
class SearchScreen(Screen):

	result_info_hashes = []

	#Predefined kivy function that gets called every time the text in the inputfield changes
	#Calls delayedSearch if the last change was over 0.5 seconds ago
	def on_txt_input(self):
		Clock.unschedule(self.delayedSearch, all=True)
		if self.ids.searchfield.text == '':
			self._reset()
		else:
			Clock.schedule_once(self.delayedSearch, 0.5)

	#Currently a filler function that gets called when a search is attempted
	#currently displays a TorrentWidget with the contents of the search
	def delayedSearch(self, dt):

		# Empty the result list:
		self._reset()

		# Starts a Tribler search for user submitted keyword:
		search_text = self.ids.searchfield.text
		torrent_mgr = globalvars.skelly.tw.get_torrent_mgr()
		torrent_mgr.subscribe_for_changed_search_results(self._on_search_results_change)
		torrent_mgr.search_remote(search_text)

	def _on_search_results_change(self, keywords):
		"""
		Called when search results have been added.
		:param keywords: The keywords entered.
		:return: Nothing.
		"""
		torrent_mgr = globalvars.skelly.tw.get_torrent_mgr()

		# Ignore old results:
		if keywords != torrent_mgr.format_keywords(self.ids.searchfield.text):
			return

		# Retrieve and show the new torrent results:
		torrents = torrent_mgr.get_remote_results()
		for torrent in torrents:
			if torrent.infohash in self.result_info_hashes:
				continue
			self.result_info_hashes.append(torrent.infohash)
			twidget = TorrentWidget()
			twidget.set_torrent(torrent)
			self.ids.fileList.add_widget(twidget)

	def _reset(self):
		self.result_info_hashes = []
		self.ids.fileList.clear_widgets()


class CameraWidget(AnchorLayout):
	passes = 0

	def __init__(self, **kwargs):
		super(CameraWidget, self).__init__(**kwargs)
		self.bind(size=self.update)
	#when the size updates, we place the camera widget appropriately
	#currently only functions after the function has been called three times, as kivy
	#does some weird stuff with updating the size variable, leading to divisions by zero
	#needs to be looked into for a more solid fix
	def update(self, *args):
		print self.passes
		print self.size
		if self.passes == 2:
			print 'Camera Size Changed to', self.size
			width_ratio = (self.size[1] * (9./16.0) )  / self.size[0]
			print width_ratio
			self._camera = AndroidCamera(size=self.size, size_hint=(width_ratio, 1))
			self.add_widget(self._camera)
			self.unbind(size=self.update)
		else:
			self.passes+=1

	#Starts Camera
	def start(self):
		print 'Start camera'
		self._camera.start()

	#Stops Camera
	def stop(self):
		print 'Stop camera'
		self._camera.stop()


class CamScreen(Screen):
	#When the screen is entered, we start the camera
	def on_enter(self):
		cam = self.ids.camera
		if cam._camera != None:
			cam.start()
	#Upon leaving, the camera is stopped
	def on_leave(self):
		cam = self.ids.camera
		if cam._camera != None:
			cam.stop()

class VideoScreen(Screen):
	pass


class Skelly(App):
	sm = ScreenManager()
	history = []
	HomeScr = HomeScreen(name='home')
	SearchScr = SearchScreen(name='search')
	CamScr = CamScreen(name='cam')
	VidScr = VideoScreen(name='video')
	TorrentInfoScr = TorrentInfoScreen(name='torrentinfo')
	sm.switch_to(HomeScr)
	#tw = TriblerWrapper()

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

	def makeLocalFolder(self):
		self.act = cast(Context, activity)
		globalvars.scanner = FileScanner(self.act)

		self.newDirec = File(Environment.getExternalStorageDirectory(), 'ShadowInternet')
		globalvars.torrentFolder = self.torrentFolder = File(self.newDirec.getAbsolutePath(), 'Torrents')
		globalvars.videoFolder = self.videoFolder = File(self.newDirec.getAbsolutePath(), 'Videos')
		self.torrentFile = File(self.torrentFolder.getAbsolutePath(), 'test.txt')
		self.videoFile = File(self.videoFolder.getAbsolutePath(), 'test.txt')

		if not self.newDirec.exists():
			print 'Creating local storage folder.'

			print 'Creating test file for torrent folder scan.'
			self.torrentFile.mkdirs()
			print 'Creating test File for video folder scan.'		
			self.videoFile.mkdirs()

			globalvars.scanner.addScanFile(self.torrentFile)
			globalvars.scanner.addScanFile(self.videoFile)
			globalvars.scanner.scanFiles()

		elif self.torrentFile.exists() and self.videoFile.exists():
			self.torrentFile.delete()
			self.videoFile.delete()

	def build(self):
		#Android back mapping
		android.map_key(android.KEYCODE_BACK,1001)
		win = Window
		win.bind(on_keyboard=self.key_handler)
		win.clearcolor = (1,1,1,1)
		globalvars.skelly = self

		self.makeLocalFolder()
		self.nfc_init()
		self.HomeScr.getStoredMedia()

		return self.sm

	#Function that helps properly implement the history function.
	#use this instead of switch_to
	def swap_to(self, Screen):
		self.history.append(self.sm.current_screen)
		self.sm.switch_to(Screen, direction='left')

	#required function by android, called when starting app
	def on_start(self):
		if globalvars.triblerfun:
			self.tw.start()

	#required function by android, called when paused for multitasking
	def on_pause(self):
		return True

	#required function by android, called when asked to stop
	def on_stop(self):
		globalvars.app_ending = True
		print "Terminating Application NOW"
		self.HomeScr.endThumbnailThread()
		if globalvars.triblerfun:
			self.tw.stop()

	#Required function by android, called when resumed from a pause
	def on_resume(self):
		#forces a refresh of the entire video list
		self.HomeScr.getStoredMedia()
		if globalvars.triblerfun:
			self.tw.start()

	#Button handler function
	#also calls history function in tandem with swap_to()
	def key_handler(self,window,keycode1, keycode2, text, modifiers):
		if keycode1 in [27,1001]:
			self.goBack()

	#History function, quits out of application if no history present
	def goBack(self):
		if len(self.history ) != 0:
			print self.history
			self.VidScr.ids.videoPlay.state = 'stop'
			self.VidScr.ids.videoPlay.source = ''
			self.sm.switch_to(self.history.pop(), direction = 'right')
		else:
			App.get_running_app().stop()


if __name__ == '__main__':
	Skelly().run()
