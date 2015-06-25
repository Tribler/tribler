
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
			cameraUri = intent.getData()
			cameraFile = File(cameraUri.getPath())

			globalvars.scanner.addScanFile(cameraFile)
			globalvars.scanner.scanFiles()
