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
	File currentApp;

	/* Method that allows the python code to attach its Activity to this Class. */
	public void addContext(Activity act){
		context = act;
		currentApp = new File(context.getPackageResourcePath());
		uris.add(Uri.fromFile(currentApp));
		System.out.println("Added APK Uri");
		System.out.println((Uri.fromFile(currentApp)).toString());
	}

	/* Method that adds an Uri to the list of Files to be sent through Android Beam. */
	public void addUris(String fileUri){
		if (!changed) {
			uris.removeAll(Uri.fromFile(currentApp));
			changed = true;
		}

		System.out.println("Add Uri: " + fileUri);
		uris.add(Uri.fromFile(new File(fileUri)));
	}

	public void removeUris(String fileUri){
		System.out.println("Remove Uri: " + fileUri);
		uris.removeAll(Uri.fromFile(new File(fileUri)));

		if (uris.isEmpty()) {
			uris.add(Uri.fromFile(currentApp));
			System.out.println("Added APK Uri");
			System.out.println((Uri.fromFile(currentApp)).toString());
			changed = false;
		}
	}

	public void clearUris(){
		System.out.println("Clearing NFC stack.");
		uris.clear();
		uris.add(Uri.fromFile(currentApp));
		System.out.println("Added APK Uri");
		System.out.println((Uri.fromFile(currentApp)).toString());
	}

	/* Method that either sends the specified Files through Android Beam or the App itself, if no Files were specified. */
	@Override
	public Uri[] createBeamUris(NfcEvent event) {
		Uri[] res = new Uri[uris.size()];
		uris.toArray(res);
		System.out.print("Sending: ");
		for(int i = 0; i < res.length; i++) {
			System.out.println(res[i].toString());
		}

		return res;
	}
}
