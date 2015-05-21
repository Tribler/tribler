package org.test;

import java.io.File;
import java.util.ArrayList;

import android.app.Activity;
import android.net.Uri;
import android.nfc.NfcAdapter;
import android.nfc.NfcEvent;

public class CreateNfcBeamUrisCallback implements NfcAdapter.CreateBeamUrisCallback {

	boolean changed = false;
	ArrayList<Uri> uris = new ArrayList<Uri>();
	Activity context;

	public void addContext(Activity act){
		context = act;
	}

	public void addUris(Uri fileUri){
		if (!changed) {
			changed = true;
		}

		System.out.println("Add Uri: " + fileUri.toString());
		uris.add(fileUri);
	}

	@Override
	public Uri[] createBeamUris(NfcEvent event) {
		if (!changed) {
			File currentApp = new File(context.getPackageResourcePath());
			uris.add(Uri.fromFile(currentApp));
			System.out.println("Added APK Uri");
			System.out.println((Uri.fromFile(currentApp)).toString());
		}

		Uri[] res = new Uri[uris.size()];
		uris.toArray(res);
		System.out.print("Sending: ");
		System.out.println((res[0]).toString());

		return res;
	}
}
