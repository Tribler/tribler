__all__ = ['AndroidWidgetHolder']

from jnius import autoclass, cast
from kivy.properties import ObjectProperty
from kivy.uix.widget import Widget
from kivy.core.window import Window

PythonActivity = autoclass('org.renpy.android.PythonActivity')
LayoutParams = autoclass('android.view.ViewGroup$LayoutParams')
LinearLayout = autoclass('android.widget.LinearLayout')

#Widget that holds the SurfaceView created for the Camera Preview
class AndroidWidgetHolder(Widget):
	view = ObjectProperty(allownone = True)

	def __init__(self, **kwargs):
		self.oldView = None
		self.window = Window
		kwargs['size_hint'] = (None, None)
		super(AndroidWidgetHolder, self).__init__(**kwargs)

	#Function that is called once the view is being shown by the App
	def on_view(self, instance, view):
		#Remove the previous View
		if self.oldView is not None:
			layout = cast(LinearLayout, self.oldView.getParent())
			layout.removeView(self.oldView)
			self.oldView = None

		#Exit is there is no view
		if view is None:
			return

		#Adjust and display the new View, then set is as the old View
		activity = PythonActivity.mActivity
		activity.addContentView(view, LayoutParams(*self.size))
		view.setZOrderOnTop(True)
		view.setX(self.x)
		view.setY(self.window.height - self.y - self.height)
		self.oldView = view

	#Function that sets the sizes of the View
	def on_size(self, instance, size):
		if self.view:
			params = self.view.getLayoutParams()
			params.width = self.width
			params.height = self.height
			self.view.setLayoutParams(params)
			self.view.setY(self.window.height - self.y - self.height)

	def on_x(self, instance, x):
		if self.view:
			self.view.setX(x)

	def on_y(self, instance, y):
		if self.view:
			self.view.setY(y)
