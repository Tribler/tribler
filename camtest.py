

from jnius import autoclass, JavaMethod, PythonJavaClass, java_method, cast

from kivy.uix.widget import Widget

PythonActivity = autoclass('org.renpy.android.PythonActivity')
AudioSource = autoclass('android.media.MediaRecorder$AudioSource')
CamcorderProfile = autoclass('android.media.CamcorderProfile')
Camera = autoclass('android.hardware.Camera')
CameraInfo = autoclass('android.hardware.Camera$CameraInfo')
CameraParameters = autoclass('android.hardware.Camera$Parameters')
CameraSize = autoclass('android.hardware.Camera$Size')
Date = autoclass('java.util.Date')
Environment = autoclass('android.os.Environment')
File = autoclass('java.io.File')
MediaRecorder = autoclass('android.media.MediaRecorder')
SimpleDateFormat = autoclass('java.text.SimpleDateFormat')
Surface = autoclass('android.view.Surface')
SurfaceView = autoclass('android.view.SurfaceView')
VideoSource = autoclass('android.media.MediaRecorder$VideoSource')

from android.runnable import run_on_ui_thread

LayoutParams = autoclass('android.view.ViewGroup$LayoutParams')
ImageFormat = autoclass('android.graphics.ImageFormat')
LinearLayout = autoclass('android.widget.LinearLayout')
Integer = autoclass('java.lang.Integer')
Double = autoclass('java.lang.Double')

from collections import namedtuple
from kivy.app import App
from kivy.properties import ObjectProperty, ListProperty, BooleanProperty, NumericProperty
from kivy.uix.widget import Widget
from kivy.uix.anchorlayout import AnchorLayout
from kivy.graphics import Color, Line
from kivy.core.window import Window

import sys

#Implementation of the PreviewCallback Interface
#Saves a Callback function to which it passes along it's input once the class is called
class PreviewCallback(PythonJavaClass):
	__javainterfaces__ = ['android.hardware.Camera$PreviewCallback']
	__javacontext__ = 'app'

	#Intialize
	def __init__(self, callback):
		super(PreviewCallback, self).__init__()
		self.callback = callback

	#Function that passes along the data and camera to the actual callback function
	@java_method('(BLandroid/hardware/Camera;)V')
	def onPreviewFrame(self, data, camera):
		self.callback(camera, data)

#Implementation of the SurfaceHolderCallback Interface
class SurfaceHolderCallback(PythonJavaClass):
	__javainterfaces__ = ['android.view.SurfaceHolder$Callback']
	__javacontext__ = 'app'

	#Initialize
	def __init__(self, callback):
		super(SurfaceHolderCallback, self).__init__()
		self.callback = callback

	#Function that passes the variables to the actual callback function
	@java_method('(Landroid/view/SurfaceHolder;III)V')
	def surfaceChanged(self, surface, frmat, width, height):
		self.callback(frmat, width, height)

	#Handled internally
	@java_method('(Landroid/view/SurfaceHolder;)V')
	def surfaceCreated(self, surface):
		pass

	#Handled internally
	@java_method('(Landroid/view/SurfaceHolder;)V')
	def surfaceDestroyed(self, surface):
		pass

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

#Class that creates and manages the Camera
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

	#Stops the recording and then closes the MediaRecorder, Camera and View
	@run_on_ui_thread
	def stop(self):
		#Check if the Camera and MediaRecorder exists and if the App is recording
		if self.vCamera is None or self.vRecorder is None or not self.recording:
			return

		#Stop the MediaRecorder and close it. Lock camera so that it can be modified.
		self.vRecorder.stop()
		self.vRecorder.reset()
		self.vRecorder.release()
		self.vRecorder = None
		self.recording = False
		self.vCamera.lock()

		#Remove previewsurface and close the Camera and View
		self.vCamera.setPreviewCallback(None)
		self.vCamera.release()
		self.vCamera = None
		self.holder.view = None

	#Start the Camera and the SurfaceView
	@run_on_ui_thread
	def start(self):
		#Checks if there is no Camera running
		if self.vCamera is not None:
			return
		#Opens the rear camera (Int value 0) and sets the proper rotation
		self.vCamera = Camera.open(0)
		self.rotation = PythonActivity.mActivity.getWindowManager().getDefaultDisplay().getRotation()
		self.vCamera.setDisplayOrientation(self.rotationDictionary(self.rotation))

		#Creates a 'fake' SurfaceView so that the Callback functions can be set
		self.surfView = SurfaceView(PythonActivity.mActivity)
		surfHolder = self.surfView.getHolder()

		#Sets the SurfaceHolderCallback to _on_surface_changed
		self.surfHolderCallback = SurfaceHolderCallback(self._on_surface_changed)
		surfHolder.addCallback(self.surfHolderCallback)

		#Attaches the View to the AndroidWidgetHolder
		self.holder.view = self.surfView

	#Override function for the SurfaceHolderCallback
	def _on_surface_changed(self, frmt, width, height):
		#Sets the proper width and height for the preview
		params = self.vCamera.getParameters()
		wantedSize = self.getOptimalPreviewSize(params.getSupportedPreviewSizes(), width, height)
		params.setPreviewSize(wantedSize.width, wantedSize.height)
		self.vCamera.setParameters(params)

		#Now that we know the camera size, we'll create 2 buffers for faster
		#result (using Callback buffer approach, as described in Camera android
		#documentation)
		#It also reduce the GC collection
		bpp = ImageFormat.getBitsPerPixel(params.getPreviewFormat()) / 8.
		buf = '\x00' * int(width * height * bpp)
		self.vCamera.addCallbackBuffer(buf)
		self.vCamera.addCallbackBuffer(buf)

		#Create a PreviewCallback to get back the onPreviewFrame into python
		self.previewCallback = PreviewCallback(self._on_preview_frame)

		#Connect the Buffer and the PreviewDisplay to the Camera
		self.vCamera.setPreviewCallbackWithBuffer(self.previewCallback)
		self.vCamera.setPreviewDisplay(self.surfView.getHolder())
		
		#Start the MediaRecorder
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

	#Function to generate an output path for a new Video
	def getOutputMediaFile(self):
		#Checks if the Storage is mounted
		if not (Environment.getExternalStorageState()).lower() == (Environment.MEDIA_MOUNTED).lower():
			return None

		#Gets file folder and creates it, if necessary
		mediaStorageDir = File(Environment.getExternalStoragePublicDirectory(Environment.DIRECTORY_DCIM), 'Camera')
		if not mediaStorageDir.exists():
			mediaStorageDir.mkdirs()

		#Create file name using a timestamp and standard file indentifiers
		timeStamp = SimpleDateFormat("yyyyMMdd_HHmmss").format(Date())
		mediaFile = File(mediaStorageDir.getPath() + File.separator + 'VID_' + timeStamp + '.mp4')

		return mediaFile

	#Function to set up the MediaRecorder
	def prepareRecorder(self):
		self.vRecorder = MediaRecorder()

		self.vCamera.unlock()
		self.vRecorder.setCamera(self.vCamera)

		#Sets the proper arguments for the MediaRecorder
		self.vRecorder.setAudioSource(AudioSource.CAMCORDER)
		self.vRecorder.setVideoSource(VideoSource.CAMERA)
		self.vRecorder.setProfile(CamcorderProfile.get(CamcorderProfile.QUALITY_HIGH))
		self.vRecorder.setOutputFile(self.getOutputMediaFile().toString())
		self.vRecorder.setPreviewDisplay(self.surfView.getHolder().getSurface())

		#Tries to connect the MediaRecorder, throws exception if it fails
		try:
			self.vRecorder.prepare()
		except Exception as ex:
			template = "An exception of type {0} occured. Arguments:\n{1!r}"
			message = template.format(type(ex).__name__, ex.args)
			print message
			return False

		return True

	#Function that obtains the Screen rotation
	def rotationDictionary(self, rotation):
		degrees = {Surface.ROTATION_0 : 0, Surface.ROTATION_90 : 90, Surface.ROTATION_180 : 180, Surface.ROTATION_270 : 270}[rotation]
		info = CameraInfo()
		Camera.getCameraInfo(0, info)

		result = (info.orientation - degrees + 360) % 360

		return result

	#Function that returns the optimal preview screen resolution, based on the preview screen size
	def getOptimalPreviewSize(self, sizes, width, height):
		ASPECT_TOLERANCE = 0.1
		targetRatio =  1.0 * width / height

		#Stop if the Camera doesn't support preview sizes
		if sizes is None:
			return None

		optimalSize = None

		minDiff = sys.float_info.max
		targetHeight = height

		#Check if one of the supported preview sizes has the same resolution as the preview screen
		#If one or more do, it picks the preview size whose height fits best within the preview screen
		for size in sizes.toArray():
			ratio = 1.0 * size.width / size.height

			if abs(ratio - targetRatio) > ASPECT_TOLERANCE:
				continue
			if abs(size.height - targetHeight) < minDiff:
				optimalSize = size
				minDiff = abs(size.height - targetHeight)

		#If none of the preview sizes has a matching resolution, it returns the preview size whose height fits best
		if optimalSize is None:
			minDiff = sys.float_info.max

			for size in sizes.toArray():
				if abs(size.height - targetHeight) < minDiff:
					optimalSize = size
					minDiff = abs(size.height - targetHeight)

		return optimalSize
