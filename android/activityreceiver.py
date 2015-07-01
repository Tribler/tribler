
from jnius import autoclass, cast, PythonJavaClass, java_method

import globalvars

Activity = autoclass('android.app.Activity')
File = autoclass('java.io.File')

#Class that handles the result from the Camera Activity that is started to record videos
class ActivityReceiver(PythonJavaClass):
	__javainterfaces__ = ['org/renpy/android/PythonActivity$ActivityResultListener']
	__javacontext__ = 'app'

	#Method that functions as the Android Activity Classes' onActivityResult method
	@java_method('(IILandroid/content/Intent;)V')
	def onActivityResult(self, requestCode, resultCode, intent):
		#If the code is the same as the one that started the Camera and the Activity succesfully captured video, save the file to local storage
		if requestCode == 1 and resultCode == Activity.RESULT_OK:
			cameraUri = intent.getData()
			cameraFile = File(cameraUri.getPath())

			globalvars.scanner.addScanFile(cameraFile)
			globalvars.scanner.scanFiles()
