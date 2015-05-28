__all__ = ('PreviewCallback', 'SurfaceHolderCallback', 'AndroidWidgetHolder', 'AndroidCamera')

from collections import namedtuple
from kivy.app import App
from kivy.properties import ObjectProperty, ListProperty, BooleanProperty, NumericProperty
from kivy.uix.widget import Widget
from kivy.uix.anchorlayout import AnchorLayout
from kivy.graphics import Color, Line
from jnius import autoclass, PythonJavaClass, java_method, cast
from android.runnable import run_on_ui_thread

# preload java classes
PythonActivity = autoclass('org.renpy.android.PythonActivity')
Camera = autoclass('android.hardware.Camera')
SurfaceView = autoclass('android.view.SurfaceView')
LayoutParams = autoclass('android.view.ViewGroup$LayoutParams')
ImageFormat = autoclass('android.graphics.ImageFormat')
LinearLayout = autoclass('android.widget.LinearLayout')


class PreviewCallback(PythonJavaClass):
    '''Interface used to get back the preview frame of the Android Camera
    '''
	__javainterfaces__ = ['android.hardware.Camera$PreviewCallback']

	def __init__(self, callback):
		super(PreviewCallback, self).__init__()
		self.callback = callback

	@java_method('([BLandroid/hardware/Camera;)V')
	def onPreviewFrame(self, data, camera):
		self.callback(camera, data)

class SurfaceHolderCallback(PythonJavaClass):
    '''Interface used to know exactly when the Surface used for the Android
    Camera will be created and changed.
    '''

	__javainterfaces__ = ['android.view.SurfaceHolder$Callback']
	__javacontext__ = 'app'

	def __init__(self, callback):
		super(SurfaceHolderCallback, self).__init__()
		self.callback = callback

	@java_method('(Landroid/view/SurfaceHolder;III)V')
	def surfaceChanged(self, surface, frmat, width, height):
		self.callback(frmat, width, height)

	@java_method('(Landroid/view/SurfaceHolder;)V')
	def surfaceCreated(self, surface):
		pass

	@java_method('(Landroid/view/SurfaceHolder;)V')
	def surfaceDestroyed(self, surface):
		pass

class AndroidWidgetHolder(Widget):
    '''Act as a placeholder for an Android widget.
    It will automatically add / remove the android view depending if the widget
    view is set or not. The android view will act as an overlay, so any graphics
    instruction in this area will be covered by the overlay.
    '''

	view = ObjectProperty(allownone=True)
	'''Must be an Android View
	'''

	def __init__(self, **kwargs):
		self._old_view = None
		from kivy.core.window import Window
		self._window = Window
		kwargs['size_hint'] = (None, None)
		super(AndroidWidgetHolder, self).__init__(**kwargs)

	def on_view(self, instance, view):
		if self._old_view is not None:
		layout = cast(LinearLayout, self._old_view.getParent())
		layout.removeView(self._old_view)
		self._old_view = None

		if view is None:
        		return

		activity = PythonActivity.mActivity
		activity.addContentView(view, LayoutParams(*self.size))
		view.setZOrderOnTop(True)
		view.setX(self.x)
		view.setY(self._window.height - self.y - self.height)
		self._old_view = view

	def on_size(self, instance, size):
		if self.view:
		params = self.view.getLayoutParams()
		params.width = self.width
		params.height = self.height
		self.view.setLayoutParams(params)
		self.view.setY(self._window.height - self.y - self.height)

	def on_x(self, instance, x):
		if self.view:
			self.view.setX(x)

	def on_y(self, instance, y):
		if self.view:
			self.view.setY(self._window.height - self.y - self.height)

class AndroidCamera(Widget):
    '''Widget for controling an Android Camera.
    '''

	index = NumericProperty(0)

	__events__ = ('on_preview_frame', )

	def __init__(self, **kwargs):
		self._holder = None
		self._android_camera = None
		super(AndroidCamera, self).__init__(**kwargs)
		self._holder = AndroidWidgetHolder(size=self.size, pos=self.pos)
		self.add_widget(self._holder)

	@run_on_ui_thread
	def stop(self):
		if self._android_camera is None:
			return
		self._android_camera.setPreviewCallback(None)
		self._android_camera.release()
		self._android_camera = None
		self._holder.view = None

	@run_on_ui_thread
	def start(self):
		if self._android_camera is not None:
			return

		self._android_camera = Camera.open(self.index)

		# create a fake surfaceview to get the previewCallback working.
		self._android_surface = SurfaceView(PythonActivity.mActivity)
		surface_holder = self._android_surface.getHolder()

		# create our own surface holder to correctly call the next method when
		# the surface is ready
		self._android_surface_cb = SurfaceHolderCallback(self._on_surface_changed)
		surface_holder.addCallback(self._android_surface_cb)

		# attach the android surfaceview to our android widget holder
		self._holder.view = self._android_surface

	def _on_surface_changed(self, fmt, width, height):
		# internal, called when the android SurfaceView is ready
		# FIXME if the size is not handled by the camera, it will failed.
		params = self._android_camera.getParameters()
		params.setPreviewSize(width, height)
		self._android_camera.setParameters(params)

		# now that we know the camera size, we'll create 2 buffers for faster
		# result (using Callback buffer approach, as described in Camera android
		# documentation)
		# it also reduce the GC collection
		bpp = ImageFormat.getBitsPerPixel(params.getPreviewFormat()) / 8.
		buf = '\x00' * int(width * height * bpp)
		self._android_camera.addCallbackBuffer(buf)
		self._android_camera.addCallbackBuffer(buf)

		# create a PreviewCallback to get back the onPreviewFrame into python
		self._previewCallback = PreviewCallback(self._on_preview_frame)

		# connect everything and start the preview
		self._android_camera.setPreviewCallbackWithBuffer(self._previewCallback);
		self._android_camera.setPreviewDisplay(self._android_surface.getHolder())
		self._android_camera.startPreview();

	def _on_preview_frame(self, camera, data):
		# internal, called by the PreviewCallback when onPreviewFrame is
		# received
		self.dispatch('on_preview_frame', camera, data)
		# reintroduce the data buffer into the queue
		self._android_camera.addCallbackBuffer(data)

	def on_preview_frame(self, camera, data):
		pass

	def on_size(self, instance, size):
		if self._holder:
			self._holder.size = size

	def on_pos(self, instance, pos):
		if self._holder:
			self._holder.pos = pos
