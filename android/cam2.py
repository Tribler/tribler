__all__ = ['']

from kivy.uix.widget import Widget
from android.runnable import run_on_ui_thread

from collections import namedtuple
from kivy.app import App
from kivy.properties import ObjectProperty, ListProperty, BooleanProperty, NumericProperty
from kivy.uix.widget import Widget
from kivy.uix.anchorlayout import AnchorLayout
from kivy.graphics import Color, Line

from jnius import autoclass, PythonJavaClass, java_method, cast

Camera = autoclass('android.hardware.Camera')
MediaRecorder = autoclass('android.media.MediaRecorder')
CamcorderProfile = autoclass('android.media.CamcorderProfile')
File = autoclass('java.io.File')
SimpleDateFormat = autoclass('java.text.SimpleDateFormat')
Date = autoclass('java.util.Date')

AudioSource = autoclass('android.media.MediaRecorder$AudioSource')
VideoSource = autoclass('android.media.MediaRecorder$VideoSource')
Environment = autoclass('android.os.Environment')
Uri = autoclass('android.net.Uri')

SurfaceView = autoclass('android.view.SurfaceView')
PythonActivity = autoclass('org.renpy.android.PythonActivity')
LayoutParams = autoclass('android.view.ViewGroup$LayoutParams')
ImageFormat = autoclass('android.graphics.ImageFormat')
LinearLayout = autoclass('android.widget.LinearLayout')

class AndroidCamera(Widget):
	__events__ = ['on_preview_frame']

	def __init__(self, **kwargs):
		self.holder = None
		self.camera = None
		self.mediaRecorder = None
		super(AndroidCamera, self).__init__(**kwargs)
		self.holder = AndroidWidgetHolder(size=self.size, pos=self.pos)
		self.add_widget(self.holder)

	@run_on_ui_thread
	def stop(self):
		if self.camera is None:
			return

		self.mediaRecorder.stop()
		self.mediaRecorder.reset()
		self.mediaRecorder.release()

		self.camera.setPreviewCallback(None)
		self.camera.release()
		self.camera = None
		self.holder.view = None

	@run_on_ui_thread
	def start(self):
		if self.camera is not None:
			return

		print 'Setting Cam'
		self.getCameraInstance(0)

		# create a fake surfaceview to get the previewCallback working.
		self.surface = SurfaceView(PythonActivity.mActivity)
		surfaceHolder = self.surface.getHolder()

		# create our own surface holder to correctly call the next method when
		# the surface is ready
		self.surfaceCallback = SurfaceHolderCallback(self._on_surface_changed)
		surfaceHolder.addCallback(self.surfaceCallback)

		# attach the android surfaceview to our android widget holder
		self.holder.view = self.surface

		if self.prepareCamera():
			self.mediaRecorder.start()

	def _on_surface_changed(self, fmt, width, height):
		# internal, called when the android SurfaceView is ready
		# FIXME if the size is not handled by the camera, it will failed.
		params = self.camera.getParameters()
		params.setPreviewSize(width, height)
		self.camera.setParameters(params)

		# now that we know the camera size, we'll create 2 buffers for faster result 
		# (using Callback buffer approach, as described in Camera android documentation)
		# it also reduce the GC collection
		bpp = ImageFormat.getBitsPerPixel(params.getPreviewFormat()) / 8.
		buf = '\x00' * int(width * height * bpp)
		self.camera.addCallbackBuffer(buf)
		self.camera.addCallbackBuffer(buf)

		# create a PreviewCallback to get back the onPreviewFrame into python
		self.previewCallback = PreviewCallback(self._on_preview_frame)

		# connect everything and start the preview
		self.camera.setPreviewCallbackWithBuffer(self.previewCallback);
		self.camera.setPreviewDisplay(self.surface.getHolder())
		self.camera.startPreview();

	def _on_preview_frame(self, camera, data):
		# internal, called by the PreviewCallback when onPreviewFrame is received
		self.dispatch('on_preview_frame', camera, data)
		# reintroduce the data buffer into the queue
		self.camera.addCallbackBuffer(data)

	def on_preview_frame(self, camera, data):
		pass

	def on_size(self, instance, size):
		if self.holder:
			self.holder.size = size

	def on_pos(self, instance, pos):
		if self.holder:
			self.holder.pos = pos

		#Return back camera if side is 1, else returns front camera
	def getCameraInstance(self, side):
		if side == 0:
			try:
				print 'Backside cam'
				self.camera = Camera.open(side)
				print self.camera
			except Exception:
				print Exception
		else:
			try:
				self.camera = Camera.open(side)
			except Exception:
				print Exception

	def prepareCamera(self):
		self.camera.unlock()
		self.mediaRecorder = MediaRecorder()

		#Step 1: Unlock and set camera to MediaRecorder
		#camera.unlock();
		self.mediaRecorder.setCamera(self.camera)

		#Step 2: Set sources
		self.mediaRecorder.setAudioSource(AudioSource.CAMCORDER)
		self.mediaRecorder.setVideoSource(VideoSource.CAMERA)

		#Step 3: Set a CamcorderProfile (requires API Level 8 or higher)
		self.mediaRecorder.setProfile(CamcorderProfile.get(CamcorderProfile.QUALITY_HIGH))

		#Step 4: Set output file
		self.mediaRecorder.setOutputFile(self.getOutputMediaFile().toString())

		for x in range(0,5):
			print 'KIJK'

		#Step 5: Set the preview output
		self.mediaRecorder.setPreviewDisplay(self.surface.getHolder().getSurface())

		try:
			self.mediaRecorder.prepare()
		except Exception as ex:
			template = "An exception of type {0} occured. Arguments:\n{1!r}"
			message = template.format(type(ex).__name__, ex.args)
			print message

		return True

	def getOutputMediaFile(self):
		if not (Environment.getExternalStorageState()).lower() == (Environment.MEDIA_MOUNTED).lower():
			return None

		print 'Kijk eens hier'

		mediaStorageDir = File(Environment.getExternalStoragePublicDirectory(Environment.DIRECTORY_MOVIES), 'SkeletonCam')

		if not mediaStorageDir.exists():
			mediaStorageDir.mkdirs()

		timeStamp = SimpleDateFormat("yyyyMMdd_HHmmss").format(Date())

		mediaFile = File(mediaStorageDir.getPath() + File.separator + 'VID_' + timeStamp + '.mp4')

		return mediaFile

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

#class setCamera():
#	camera = AndroidCamera(size=self.camera_size, size_hint=(None, None))
#	mediaRecorder = MediaRecorder()

	#Step 1: Unlock and set camera to MediaRecorder
	#camera.unlock();
#	mediaRecorder.setCamera(camera)

	#Step 2: Set sources
#	mediaRecorder.setAudioSource(MediaRecorder.AudioSource.CAMCORDER)
#	mediaRecorder.setVideoSource(MediaRecorder.VideoSource.CAMERA)

	#Step 3: Set a CamcorderProfile (requires API Level 8 or higher)
#	mediaRecorder.setProfile(CamcorderProfile.get(CamcorderProfile.QUALITY_HIGH))

	#Step 4: Set output file
#	mediaRecorder.setOutputFile(getOutputMediaFile(MEDIA_TYPE_VIDEO).toString())

	#Step 5: Set the preview output
	#mediaRecorder.setPreviewDisplay(mPreview.getHolder().getSurface())

#	def startCamera():
#		mediaRecorder.start()

#	def stopCamera():
#		mediaRecorder.stop()	

#	def getOutputMediaFile(self):
#		if not (Environment.getExternalStorageState()).lower() == (Environment.MEDIA_MOUNTED).lower():
#			return None

#		mediaStorageDir = File(Environment.getExternalStoragePublicDirectory(Environment.DIRECTORY_VIDEOS), "SkeletonCam")

#		timeStamp = SimpleDateFormat("yyyyMMdd_HHmmss").format(Date())
#		mediaFile = File()

#		mediaFile = File(mediaStorageDir.getPath() + File.separator + 'VID_' + timeStamp + '.mp4')

#		return mediaFile

class PreviewCallback(PythonJavaClass):
	#Interface used to get back the preview frame of the Android Camera

	__javainterfaces__ = ['android.hardware.Camera$PreviewCallback']
	__javacontext__ = 'app'

	def __init__(self, callback):
		super(PreviewCallback, self).__init__()
		self.callback = callback

	@java_method('([BLandroid/hardware/Camera;)V')
	def onPreviewFrame(self, data, camera):
		self.callback(camera, data)

class SurfaceHolderCallback(PythonJavaClass):
	#Interface used to know exactly when the Surface used for the Android Camera will be created and changed.

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
