__version__ = '1.0'
from kivy.app import App
from kivy.uix.screenmanager import ScreenManager, Screen
from kivy.uix.boxlayout import BoxLayout
from kivy.lang import Builder

from jnius import autoclass, cast
from jnius import JavaClass
from jnius import PythonJavaClass

mContext = autoclass('android.content.Context')
PythonActivity = autoclass('org.renpy.android.PythonActivity')
activity = PythonActivity.mActivity
Intent = autoclass('android.content.Intent')
  
Builder.load_file('main.kv')


class HomeScreen(Screen):

	def likeMore(self):
		self.ids.button1.text = self.ids.button1.text+"!"
	def AndroidTest(self):
		vibrator = activity.getSystemService(mContext.VIBRATOR_SERVICE)
		vibrator.vibrate(10000)

class CameraScreen(Screen):
	mMediaStore = autoclass('android.provider.MediaStore')
	def startCamera(self):

		intention = Intent(self.mMediaStore.ACTION_VIDEO_CAPTURE)
		self.con = cast(mContext, PythonActivity.mActivity)			
		intention.resolveActivity(con.getPackageManager())	
		if intention.resolveActivity(con.getPackageManager()) != None:
			activity.startActivityForResult(intention,1)
class NfcScreen(Screen):
	mNfcAdapter = autoclass('android.nfc.NfcAdapter')


sm = ScreenManager()
sm.add_widget(HomeScreen(name='home'))
sm.add_widget(CameraScreen(name="cam"))
sm.add_widget(NfcScreen(name='nfc'))



class Skelly(App):

	def build(self):
		return sm

if __name__== '__main__':
	Skelly().run()
