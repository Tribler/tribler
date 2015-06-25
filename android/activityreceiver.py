
from jnius import autoclass, cast, PythonJavaClass, java_method

import globalvars

Activity = autoclass('android.app.Activity')
File = autoclass('java.io.File')

class ActivityReceiver(PythonJavaClass):
	__javainterfaces__ = ['org/renpy/android/PythonActivity$ActivityResultListener']
	__javacontext__ = 'app'

	@java_method('(IILandroid/content/Intent;)V')
	def onActivityResult(self, requestCode, resultCode, intent):
		if requestCode == 1 and resultCode == Activity.RESULT_OK:
			print 'Intent'
			print intent
			cameraUri = intent.getData()
			cameraFile = File(cameraUri.getPath())

			print 'Retrieved'
			print cameraUri.getPath()
			print cameraFile.getAbsolutePath()

			videoFile = File(globalvars.videoFolder, cameraFile.getName())
			if videoFile.exists():
				videoFile.delete()
			print 'Moving'
			print cameraFile.getAbsolutePath()
			print 'to Videos as'
			print videoFile.getAbsolutePath()
			print cameraFile.renameTo(videoFile)
			globalvars.scanner.addScanFile(videoFile)
			
			cameraFile.delete()
			globalvars.scanner.addScanFile(cameraFile)
			globalvars.scanner.scanFiles()
