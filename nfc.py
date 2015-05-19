__all__ = ('CreateBeamUrisCallback')

from jnius import PythonJavaClass, java_method, autoclass, cast

PythonActivity = autoclass('org.renpy.android.PythonActivity')
mContext = autoclass('android.content.Context')
NfcAdapter = autoclass('android.nfc.NfcAdapter')
NfcManager = autoclass('android.nfc.NfcManager')
Intent = autoclass('android.content.Intent')

class CreateNfcBeamUrisCallback(PythonJavaClass):
	__javainterfaces__ = ['android/nfc/NfcAdapter$CreateBeamUrisCallback']
	__javacontext__ = 'app'

	def __init__(self):
		super(CreateNfcBeamUrisCallback, self).__init__()

		self.manager = cast('android.nfc.NfcManager', PythonActivity.mActivity.getSystemService(mContext.NFC_SERVICE))
		
		self.do_stop = False
		self.adapter = self.manager.getDefaultAdapter()

		if self.adapter is None:
			print 'This device does not support NFC.'
			return
		else:
			print 'This device does support NFC.'
			self.adapter.setBeamPushUrisCallback(self, PythonActivity.mActivity)

	def start(self):
		self.do_stop = False
		
		if NfcAdapter.ACTION_NDEF_DISCOVERED.equals(PythonActivity.mActivity.getIntent().getAction()):
			pass

	@java_method('(Landroid/nfc/NfcEvent;)[android.net.Uri')
	def createBeamUris(self, event):
		if self.do_stop:
			print 'NFC did not act on Event, App not active.'
			return

		
		return None
