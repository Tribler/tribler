__version__ = '1.0'
from kivy.app import App
from kivy.uix.button import Button
from kivy.uix.screenmanager import ScreenManager, Screen
from kivy.uix.boxlayout import BoxLayout
from kivy.lang import Builder

from jnius import autoclass
mContext = autoclass('android.content.Context')
PythonActivity = autoclass('org.renpy.android.PythonActivity')
activity = PythonActivity.mActivity
Intent = autoclass('android.content.Intent')
mMediaStore = autoclass('android.provider.MediaStore')
mComponentName = autoclass('android.content.ComponentName')
mPackageManager = autoclass('android.content.pm.PackageManager')
  
#class Hello(App):
#    def build(self):
#        btn = Button(text='Hello World')
 #       return  btn
  
#Hello().run()
Builder.load_file('main.kv')


class HomeScreen(Screen):

	def likeMore(self):
		self.ids.button1.text = self.ids.button1.text+"!"
	def AndroidTest(self):
		vibrator = activity.getSystemService(mContext.VIBRATOR_SERVICE)
		vibrator.vibrate(10000)

class CameraScreen(Screen):

	def startCamera(self):
		intention = Intent()
		intention.setAction(mMediaStore.ACTION_VIDEO_CAPTURE)
		#intention = Intent(mMediaStore.ACTION_VIDEO_CAPTURE)
		#con = mContext		
		print 'Context:'		
		#print con
		print 'PM:'
		#print con.getPackageManager()
		print 'intent:'		
		print intention
		print intention.resolveActivity
		print 'cm'
		#cm = intention.resolveActivity(mContext.getPackageManager())
		print 'cm!'
		#print cm		
		#if cm.toString() != None:
			#pass
		activity.startActivityForResult(intention,1)

sm = ScreenManager()
sm.add_widget(HomeScreen(name='home'))
sm.add_widget(CameraScreen(name="cam"))



class Skelly(App):

	def build(self):
		return sm

if __name__== '__main__':
	Skelly().run()
