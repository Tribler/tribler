from jnius import autoclass, cast, PythonJavaClass, java_method

Array = autoclass('java.util.Arrays')
File = autoclass('java.io.File')
MediaScannerConnection = autoclass('android.media.MediaScannerConnection')

class FileScanner(PythonJavaClass):
	__javainterfaces__ = ['android/media/MediaScannerConnection$MediaScannerConnectionClient']
	__javacontext__ = 'app'

	def __init__(self, con):
		super(FileScanner, self).__init__()
		self.context = con
		self.connected = False
		self.paths = []

	def addScanFile(self, sfile):
		self.paths.append(sfile.getAbsolutePath())

	def scanFiles(self):	
		if not self.connected:
			print 'Connecting to MediaScanner'
			self.connected = True
			self.mediaConnection = MediaScannerConnection(self.context, self)
			self.mediaConnection.connect()

	def sendScan(self):
		print 'Scanning: '
		package = self.paths.pop()
		print package
		self.mediaConnection.scanFile(package, None)

	@java_method('()V')
	def onMediaScannerConnected(self):
		print 'MediaScannerConnection has been established.'
		self.sendScan()

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
