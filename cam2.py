__all__ = ['']

from jnius import autoclass, PythonJavaClass, java_method, cast

Camera = autoclass('android.hardware.Camera')
MediaRecorder = autoclass('android.media.MediaRecorder')
CamcorderProfile = autoclass('android.media.CamcorderProfile')
File = autoclass('java.io.File')
SimpleDateFormat = autoclass('java.text.SimpleDateFormat')
Date = autoclass('java.util.Date')

class createCam():
	camera = getCameraInstance(1)
	mediaRecorder = MediaRecorder()

	#Step 1: Unlock and set camera to MediaRecorder
	#camera.unlock();
	mediaRecorder.setCamera(camera);

	#Step 2: Set sources
	mediaRecorder.setAudioSource(MediaRecorder.AudioSource.CAMCORDER)
	mediaRecorder.setVideoSource(MediaRecorder.VideoSource.CAMERA)

	#Step 3: Set a CamcorderProfile (requires API Level 8 or higher)
	mediaRecorder.setProfile(CamcorderProfile.get(CamcorderProfile.QUALITY_HIGH))

	#Step 4: Set output file
	mediaRecorder.setOutputFile(getOutputMediaFile(MEDIA_TYPE_VIDEO).toString())

	#Step 5: Set the preview output
	mediaRecorder.setPreviewDisplay(mPreview.getHolder().getSurface())

	#Return back camera if side is 1, else returns front camera
	def getCameraInstance(self, side):
		if side == 1:
			return Camera.open(Camera.CameraInfo.CAMERA_FACING_BACK)
		else:
			return Camera.open(Camera.CameraInfo.CAMERA_FACING_FRONT)

	def getOutputMediaFile(self):
		if not (Environment.getExternalStorageState()).lower() == (Environment.MEDIA_MOUNTED).lower():
			return None

		mediaStorageDir = File(Environment.getExternalStoragePublicDirectory(Environment.DIRECTORY_VIDEOS), "CameraSample")

		timeStamp = SimpleDateFormat("yyyyMMdd_HHmmss").format(Date())
		mediaFile = File()

		mediaFile = File(mediaStorageDir.getPath() + File.separator + 'VID_' + timeStamp + '.mp4')

		return mediaFile
