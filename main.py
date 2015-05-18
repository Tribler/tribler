__version__ = '1.0'
from kivy.app import App
from kivy.uix.screenmanager import ScreenManager, Screen
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.widget import Widget
from kivy.core.window import Window
from kivy.lang import Builder
from kivy.uix.button import Button
import android
import os


from jnius import autoclass, cast
from jnius import JavaClass
from jnius import PythonJavaClass

mContext = autoclass('android.content.Context')
PythonActivity = autoclass('org.renpy.android.PythonActivity')
activity = PythonActivity.mActivity
Intent = autoclass('android.content.Intent')
mEnvironment = autoclass('android.os.Environment')
NfcAdapter = autoclass('android.nfc.NfcAdapter')
Bundle = autoclass('android.os.Bundle')
Uri = autoclass('android.net.Uri')
Builder.load_file('main.kv')


class HomeScreen(Screen):
	mMediaStore = autoclass('android.provider.MediaStore')
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

		intention = Intent(self.mMediaStore.ACTION_VIDEO_CAPTURE)
		self.con = cast(mContext, activity)			
		intention.resolveActivity(self.con.getPackageManager())	
		if intention.resolveActivity( self.con.getPackageManager()) != None:
			activity.startActivityForResult(intention,1)
	ButtonNumber = 0
	def addVideo(self):
		wid = FileWidget()
		wid.setName('Name %d' % self.ButtonNumber)
		self.ButtonNumber = self.ButtonNumber+1
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
	mFile = autoclass('java.io.File')

	def printDir(self):	
		DCIMdir = mEnvironment.getExternalStoragePublicDirectory(mEnvironment.DIRECTORY_DCIM)
		print DCIMdir.list()

		self.con = cast(mContext, activity)
		mNfcAdapter = NfcAdapter.getDefaultAdapter(self.con)
		if mNfcAdapter is None:
			print 'Device does not support NFC.'
		else:
			print mNfcAdapter

class MainActivity(JavaClass):
	__javainterfaces__ = ['android/os/Activity']

	testUri = ''
	filename = ''
	filelocation = 'content://..../'

	def __init__(self):
		super(MainActivity, self).__init__()

	def onCreate(savedInstanceState):
		sIS = cast(Bundle, savedInstanceState)
		#Niet zeker of onderstaande regel nodig is (als het goed is overriden wij de functie zowiezo al door dezelfde naam te hebben
		#super(onCreate, self).onCreate(sIs)
		self.con = cast(mContext, activity)
		mNfcAdapter = NfcAdapter.getDefaultAdapter(self.con)

		if mNfcAdapter is None:
			print 'NFC is not supported on this device.'
			return
		else:
			print 'NFC is supported on this device.'
			mNfcAdapter.setBeamPushUrisCallback(self, self.con)

	def createBeamUris(nfcEvent):
		testUri = Uri.parse(filelocation % filename)
		return photoUri

class FileWidget(BoxLayout):
	name = 'NO FILENAME SET'
	uri = None
	thumbnail = None  #Gotta make a default for this later
	def setName(self, nom):
		self.name = nom
		self.ids.filebutton.text = nom
	def setUri(self,ur):
		self.uri = ur
	def setThumb(self,thumb):
		self.thumbnail = thumb
		




class Skelly(App):
	sm = ScreenManager()
	history = []
	HomeScr = HomeScreen(name='home')
	NfcScr = NfcScreen(name='nfc')
	sm.switch_to(HomeScr)

	def build(self):
		android.map_key(android.KEYCODE_BACK,1001)
		win = Window
		win.bind(on_keyboard=self.key_handler)
		return self.sm
	def swap_to(self, Screen):
		self.history.append(self.sm.current_screen)
		self.sm.switch_to(Screen, direction='left')

	def on_pause(self):
		return True
	def on_stop(self):
		pass
	def on_resume(self):
		pass
	def key_handler(self,window,keycode1, keycode2, text, modifiers):
		if keycode1 in [27,1001]:
			if len(self.history ) != 0:
				print self.history
				self.sm.switch_to(self.history.pop(), direction = 'right')				
			else:
				App.get_running_app().stop()

if __name__== '__main__':
	Skelly().run()
