

from jnius import autoclass, JavaMethod, PythonJavaClass, java_method, cast

from kivy.uix.widget import Widget

PythonActivity = autoclass('org.renpy.android.PythonActivity')
AudioSource = autoclass('android.media.MediaRecorder$AudioSource')
CamcorderProfile = autoclass('android.media.CamcorderProfile')
Camera = autoclass('android.hardware.Camera')
CameraParameters = autoclass('android.hardware.Camera$Parameters')
CameraSize = autoclass('android.hardware.Camera$Size')
Date = autoclass('java.util.Date')
Environment = autoclass('android.os.Environment')
File = autoclass('java.io.File')
MediaRecorder = autoclass('android.media.MediaRecorder')
SimpleDateFormat = autoclass('java.text.SimpleDateFormat')
SurfaceView = autoclass('android.view.SurfaceView')
VideoSource = autoclass('android.media.MediaRecorder$VideoSource')

from android.runnable import run_on_ui_thread

LayoutParams = autoclass('android.view.ViewGroup$LayoutParams')
ImageFormat = autoclass('android.graphics.ImageFormat')
LinearLayout = autoclass('android.widget.LinearLayout')

from collections import namedtuple
from kivy.app import App
from kivy.properties import ObjectProperty, ListProperty, BooleanProperty, NumericProperty
from kivy.uix.widget import Widget
from kivy.uix.anchorlayout import AnchorLayout
from kivy.graphics import Color, Line
from kivy.core.window import Window

class PreviewCallback(PythonJavaClass):
	__javainterfaces__ = ['android.hardware.Camera$PreviewCallback']
	__javacontext__ = 'app'

	def __init__(self, callback):
		super(PreviewCallback, self).__init__()
		self.callback = callback
	
	@java_method('(BLandroid/hardware/Camera;):V')
	def onPreviewFrame(self, data, camera):
		self.callback(camera, data)

class SurfaceHolderCallback(PythonJavaClass):
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
	view = ObjectProperty(allownone = True)

	def __init__(self, **kwargs):
		self.oldView = None
		self.window = Window
		kwargs['size_hint'] = (None, None)
		super(AndroidWidgetHolder, self).__init__(**kwargs)

	def on_view(self, instance, view):
		if self.oldView is not None:
			layout = cast(LinearLayout, self.oldView.getParent())
			layout.removeView(self.oldView)
			self.oldView = None

		if view is None:
			return

		activity = PythonActivity.mActivity
		activity.addContentView(view, LayoutParams(*self.size))
		view.setZOrderOnTop(True)
		view.setX(self.x)
		view.setY(self.window.height - self.y - self.height)
		self.oldView = view

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

class CamTestCamera(Widget):
	__events__ = ['on_preview_frame']

	def __init__(self, **kwargs):
		self.holder = None
		self.vCamera = None
		self.vRecorder = None
		self.recording = False
		super(CamTestCamera, self).__init__(**kwargs)
		self.holder = AndroidWidgetHolder(size = self.size, pos = self.pos)
		self.add_widget(self.holder)

	@run_on_ui_thread
	def stop(self):
		if self.vCamera is None or self.vRecorder is None or not self.recording:
			return

		self.vRecorder.stop()
		self.vRecorder.reset()
		self.vRecorder.release()
		self.vRecorder = None
		self.recording = False
		self.vCamera.lock()

		self.vCamera.setPreviewCallback(None)
		self.vCamera.release()
		self.vCamera = None
		self.holder.view = None

	@run_on_ui_thread
	def start(self):
		if self.vCamera is not None:
			return

		self.vCamera = Camera.open(0)

		self.surfView = SurfaceView(PythonActivity.mActivity)
		surfHolder = self.surfView.getHolder()

		self.surfHolderCallback = SurfaceHolderCallback(self._on_surface_changed)
		surfHolder.addCallback(self.surfHolderCallback)

		self.holder.view = self.surfView

	def _on_surface_changed(self, frmt, width, height):
		params = self.vCamera.getParameters()
		params.setPreviewSize(width, height)
		self.vCamera.setParameters(params)

		# now that we know the camera size, we'll create 2 buffers for faster
		# result (using Callback buffer approach, as described in Camera android
		# documentation)
		# it also reduce the GC collection
		bpp = ImageFormat.getBitsPerPixel(params.getPreviewFormat()) / 8.
		buf = '\x00' * int(width * height * bpp)
		self.vCamera.addCallbackBuffer(buf)
		self.vCamera.addCallbackBuffer(buf)

		# create a PreviewCallback to get back the onPreviewFrame into python
		self.previewCallback = PreviewCallback(self._on_preview_frame)

		# connect everything and start the preview
		self.vCamera.setPreviewCallbackWithBuffer(self.previewCallback)
		self.vCamera.setPreviewDisplay(self.surfView.getHolder())
		
		if self.prepareRecorder():
			self.vRecorder.start()
			self.recording = True

	def _on_preview_frame(self, camera, data):
		self.dispatch('on_preview_frame', camera, data)
		self.vCamera.addCallbackBuffer(data)

	def on_preview_frame(self, camera, data):
		pass

	def on_size(self, instance, size):
		if self.holder:
			self.holder.size = size

	def on_pos(self, instance, pos):
		if self.holder:
			self.holder.pos = pos

	def getOutputMediaFile(self):
		if not (Environment.getExternalStorageState()).lower() == (Environment.MEDIA_MOUNTED).lower():
			return None

#		mediaStorageDir = File(Environment.getExternalStoragePublicDirectory(Environment.DIRECTORY_MOVIES), 'SkeletonCam')
		mediaStorageDir = File(Environment.getExternalStoragePublicDirectory(Environment.DIRECTORY_DCIM), 'Camera')
		if not mediaStorageDir.exists():
			mediaStorageDir.mkdirs()

		timeStamp = SimpleDateFormat("yyyyMMdd_HHmmss").format(Date())

		mediaFile = File(mediaStorageDir.getPath() + File.separator + 'VID_' + timeStamp + '.mp4')

		for x in range(0,5):
			print 'File location = ' + mediaFile.toString()

		return mediaFile

	def prepareRecorder(self):
		self.vRecorder = MediaRecorder()

		self.vCamera.unlock()
		self.vRecorder.setCamera(self.vCamera)

		self.vRecorder.setAudioSource(AudioSource.CAMCORDER)
		self.vRecorder.setVideoSource(VideoSource.CAMERA)
		self.vRecorder.setProfile(CamcorderProfile.get(CamcorderProfile.QUALITY_HIGH))
		self.vRecorder.setOutputFile(self.getOutputMediaFile().toString())
		self.vRecorder.setPreviewDisplay(self.surfView.getHolder().getSurface())

		try:
			self.vRecorder.prepare()
		except Exception as ex:
			template = "An exception of type {0} occured. Arguments:\n{1!r}"
			message = template.format(type(ex).__name__, ex.args)
			print message
			return False

		return True
