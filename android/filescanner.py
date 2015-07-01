from jnius import autoclass, cast, PythonJavaClass, java_method

Array = autoclass('java.util.Arrays')
File = autoclass('java.io.File')
MediaScannerConnection = autoclass('android.media.MediaScannerConnection')

#Class that scans the File changes that application makes to the MediaStore, so that the system can see the changes
class FileScanner(PythonJavaClass):
	__javainterfaces__ = ['android/media/MediaScannerConnection$MediaScannerConnectionClient']
	__javacontext__ = 'app'

	def __init__(self, con):
		super(FileScanner, self).__init__()
		self.context = con
		self.connected = False
		self.paths = []

	#Method that adds the filepath to the pathlist from a File
	def addScanFile(self, sfile):
		self.paths.append(sfile.getAbsolutePath())

	#Method to start the filescanning process
	def scanFiles(self):	
		if not self.connected:
			print 'Connecting to MediaScanner'
			# Paths are reversed. This is done to make the adding of files be more natural, as one can 
			# first add the new or copied files and afterwards delete the old ones. If the reversal is 
			# not done, copying a file would result in errors, as one would first delete the original 
			# file and afterwards try to copy it.
			self.paths.reverse()
			self.connected = True
			self.mediaConnection = MediaScannerConnection(self.context, self)
			self.mediaConnection.connect()

	#Method that takes the first item (as the list is reversed) and scans it to the MediaStore
	def sendScan(self):
		if len(self.paths) == 0:
			print 'No files to scan.'
			return
		print 'Scanning: '
		package = self.paths.pop()
		print package
		self.mediaConnection.scanFile(package, None)

	#Method called when the MediaConnection succesfully starts. The method starts the filescanning process.
	@java_method('()V')
	def onMediaScannerConnected(self):
		print 'MediaScannerConnection has been established.'
		self.sendScan()

	#Method called when a scan is completed. If more files have to be scanned, it scans those. Otherwise it kills the connection.
	@java_method('(Ljava/lang/String;Landroid/net/Uri;)V')
	def onScanCompleted(self, path, uri):
		print 'Succesfully scanned: '
		print uri
		print path

		if not len(self.paths) == 0:
			self.sendScan()
		else:
			self.mediaConnection.disconnect()
			self.connected = False
