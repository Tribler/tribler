__all__ = ('CreateNfcBeamUrisCallback')

from jnius import PythonJavaClass, java_method, autoclass, cast

PythonActivity = autoclass('org.renpy.android.PythonActivity')
mContext = autoclass('android.content.Context')
NfcAdapter = autoclass('android.nfc.NfcAdapter')
NfcManager = autoclass('android.nfc.NfcManager')
Intent = autoclass('android.content.Intent')
Uri = autoclass('android.net.Uri')
File = autoclass('java.io.File')
Object = autoclass('java.lang.Object')

class CreateNfcBeamUrisCallback(PythonJavaClass):
	__javainterfaces__ = ['android/nfc/NfcAdapter$CreateBeamUrisCallback']
	__javacontext__ = 'app'

	def __init__(self):
		super(CreateNfcBeamUrisCallback, self).__init__()

		self.uris = []
		self.changed = False	

#	def __init__(self):
#		super(CreateNfcBeamUrisCallback, self).__init__()
#
#		self.manager = cast('android.nfc.NfcManager', PythonActivity.mActivity.getSystemService(mContext.NFC_SERVICE))
#
#		self.do_stop = False
#		self.adapter = self.manager.getDefaultAdapter()
#
#		if self.adapter is None:
#			print 'This device does not support NFC.'
#			return
#		else:
#			print 'This device does support NFC.'
#			self.adapter.setBeamPushUrisCallback(self, PythonActivity.mActivity)
#
#	def start(self):
#		self.do_stop = False
#
#		for x in range(0,5):
#			print 'Def Start'
#
#		if NfcAdapter.ACTION_NDEF_DISCOVERED.equals(PythonActivity.mActivity.getIntent().getAction()):
#			pass

	@java_method('()I')
	def hashCode(self):
		return id(self)

	def addUris(self, fileUri):
		if not self.changed:
			self.uris = [cast(Uri, fileUri)]
			self.changed = True
		else:
			self.uris.append(cast(Uri, fileUri))

	@java_method('(Landroid/nfc/NfcEvent;)[Landroid/net/Uri;')
	def createBeamUris(self, event):
		for x in range(0,5):
			print 'createBeams'

		if not self.changed:
			context = PythonActivity.mActivity
			currentApp = File((cast(mContext, context)).getPackageResourcePath())
			self.uris[0] = cast(Uri, Uri.fromFile(currentApp))

			print Uri.decode(self.uris[0].getEncodedPath())

		return self.uris
