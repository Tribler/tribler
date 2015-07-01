__all__ = ['CameraHelper']

from jnius import autoclass
import sys
import globalvars

Camera = autoclass('android.hardware.Camera')
CameraInfo = autoclass('android.hardware.Camera$CameraInfo')
Date = autoclass('java.util.Date')
Environment = autoclass('android.os.Environment')
File = autoclass('java.io.File')
SimpleDateFormat = autoclass('java.text.SimpleDateFormat')
Surface = autoclass('android.view.Surface')

class CameraHelper(object):
	#Function to generate an output path for a new Video
	def getOutputMediaFile(self):
		#Create file name using a timestamp and standard file indentifiers
		timeStamp = SimpleDateFormat("yyyyMMdd_HHmmss").format(Date())
		mediaFile = File(globalvars.videoFolder.getPath() + File.separator + 'VID_' + timeStamp + '.mp4')

		return mediaFile

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
