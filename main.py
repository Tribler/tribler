__version__ = '1.0'
from kivy.app import App
from kivy.uix.button import Button
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
#mMediaStore = autoclass('android.provider.MediaStore')
#mComponentName = autoclass('android.content.ComponentName')
#mPackageManager = autoclass('android.content.pm.PackageManager')
  
Builder.load_file('main.kv')


class HomeScreen(Screen):

	def likeMore(self):
		self.ids.button1.text = self.ids.button1.text+"!"
	def AndroidTest(self):
		vibrator = activity.getSystemService(mContext.VIBRATOR_SERVICE)
		vibrator.vibrate(10000)

class CameraScreen(Screen):
	#Intent = autoclass('android.content.Intent')
	#PythonActivity = autoclass('org.renpy.android.PythonActivity')
	#activity = PythonActivity.mActivity
	#Intent = autoclass('android.content.Intent')
	mMediaStore = autoclass('android.provider.MediaStore')
	#mPackageManager = autoclass('android.content.pm.PackageManager')
	#mComponentName = autoclass('android.content.ComponentName')
	#mContext = autoclass('android.content.Context')
	
	def startCamera(self):
		intention = Intent(self.mMediaStore.ACTION_VIDEO_CAPTURE)
		self.con = cast(mContext, PythonActivity.mActivity)			
		intention.resolveActivity(mContext.getPackageManager())	
		if intention.resolveActivity(mContext.getPackageManager()) != None:
			activity.startActivityForResult(intention,1)

sm = ScreenManager()
sm.add_widget(HomeScreen(name='home'))
sm.add_widget(CameraScreen(name="cam"))



class Skelly(App):

	def build(self):
		return sm

if __name__== '__main__':
	Skelly().run()
