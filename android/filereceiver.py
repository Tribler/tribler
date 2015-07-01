
from jnius import autoclass, cast, PythonJavaClass, java_method

import globalvars

PythonActivity = autoclass('org.renpy.android.PythonActivity')
activity = PythonActivity.mActivity
Context = autoclass('android.content.Context')
File = autoclass('java.io.File')
Intent = autoclass('android.content.Intent')
MediaColumns = autoclass('android.provider.MediaStore$MediaColumns')
MediaStore = autoclass('android.provider.MediaStore')

class FileReceiver(PythonJavaClass):
	__javainterfaces__ = ['org/renpy/android/PythonActivity$NewIntentListener']
	__javacontext__ = 'app'

	@java_method('(Landroid/content/Intent;)V')
	def onNewIntent(self, intent):
		#Method that can be used to parse the intent and pass it to the relevant function.
		print 'Received new Intent.'
		self.action = intent.getAction()

		#If application starts normally
		if self.action == Intent.ACTION_MAIN:
			print 'Normal starting Intent'
			return
		#If application start with or receives Action_View Intent (currently through Android Beam)
		elif self.action == Intent.ACTION_VIEW:
			self.handleViewIntent(intent)

		#Following code can be added if other types of Intents are filtered
		#elif self.action == Intent. 'relevant intent type':
		#	do function

	#Method for handling the Action_VIEW Intent
	def handleViewIntent(self, intent):
		self.beamUri = intent.getData()

		#Do nothing if a file was sent
		if self.beamUri.getScheme() == 'file':
			pass

		#Retrieve the files sent if it is a video and then proceed to move them to the correct folder
		elif self.beamUri.getScheme() == 'content':
			self.beamFile = self.handleContentUri(self.beamUri)

			self.parentFile = self.beamFile.getParentFile()

			#If several files (video and torrent) were sent
			if not self.parentFile.getName() == 'beam':
				self.files = self.parentFile.listFiles()

				for f in self.files:
					print 'Moving file:'
					print f.getAbsolutePath()
					if '.torrent' in f.getName():
						torrentFile = File(globalvars.torrentFolder, f.getName())
						if torrentFile.exists():
							torrentFile.delete()

						print 'to Torrents as'
						print torrentFile.getAbsolutePath()
						print f.renameTo(torrentFile)
						globalvars.scanner.addScanFile(torrentFile)

					else:
						videoFile = File(globalvars.videoFolder, f.getName())
						if videoFile.exists():
							videoFile.delete()

						print 'to Videos as'
						print videoFile.getAbsolutePath()
						print f.renameTo(videoFile)
						globalvars.scanner.addScanFile(videoFile)

				print 'Delete folder'
				print self.parentFile.delete()
				globalvars.scanner.addScanFile(self.parentFile)

			#Else scan a single video
			else:
				videoFile = File(globalvars.videoFolder, self.beamFile.getName())
				if videoFile.exists():
					videoFile.delete()

				print 'to Videos as'
				print videoFile.getAbsolutePath()
				print self.beamFile.renameTo(videoFile)
				globalvars.scanner.addScanFile(videoFile)
				globalvars.scanner.addScanFile(self.beamFile)

			globalvars.scanner.scanFiles()

	#Method that retrieves the sent video file from the MediaStore provider
	def handleContentUri(self, uri):
		if not uri.getAuthority() == MediaStore.AUTHORITY:
			print 'Not MediaStore Authority.'

		else:
			print 'MediaStore Authority.'

			self.context = cast(Context, activity)
			projection = [MediaColumns.DATA]
			pathCursor = self.context.getContentResolver().query(uri, projection, None, None, None)

			if not pathCursor is None and pathCursor.moveToFirst():
				filenameIndex = pathCursor.getColumnIndex(MediaColumns.DATA)

				fileName = pathCursor.getString(filenameIndex)
				copiedFile = File(fileName)	
				print copiedFile.getAbsolutePath()

				return copiedFile

			else:
				return None
