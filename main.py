__version__ = '1.0'
from kivy.app import App
from kivy.uix.button import Button
from kivy.uix.screenmanager import ScreenManager, Screen
from kivy.uix.boxlayout import BoxLayout
from kivy.lang import Builder

from jnius import autoclass
Context = autoclass('android.content.Context')
PythonActivity = autoclass('org.renpy.android.PythonActivity')
  
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
		activity = PythonActivity.mActivity
		vibrator = activity.getSystemService(Context.VIBRATOR_SERVICE)
		vibrator.vibrate(10000)

class CameraScreen(Screen):
	pass

sm = ScreenManager()
sm.add_widget(HomeScreen(name='home'))
sm.add_widget(CameraScreen(name="cam"))



class Skelly(App):

	def build(self):
		return sm

if __name__== '__main__':
	Skelly().run()
