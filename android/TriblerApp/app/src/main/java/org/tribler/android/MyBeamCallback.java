package org.tribler.android;

import java.io.File;
import java.util.ArrayList;
import java.util.List;

import android.app.Activity;
import android.content.pm.PackageManager;
import android.net.Uri;
import android.nfc.NfcAdapter;
import android.nfc.NfcEvent;

public class MyBeamCallback implements NfcAdapter.CreateBeamUrisCallback {

    private boolean mAndroidBeamAvailable;
    private NfcAdapter mNfcAdapter;
    private List<Uri> outbox;

    public MyBeamCallback(Activity activity) {
        if (!activity.getPackageManager().hasSystemFeature(PackageManager.FEATURE_NFC)) {
            /*
             * Disable NFC features here.
             * For example, disable menu items or buttons that activate
             * NFC-related features
             */
            mAndroidBeamAvailable = false;
        } else {
            mAndroidBeamAvailable = true;
            mNfcAdapter = NfcAdapter.getDefaultAdapter(activity);
            mNfcAdapter.setBeamPushUrisCallback(this, activity);
        }
        // Initialize outbox to prevent null-pointers if one forgets to check if Beam is available
        this.outbox = new ArrayList<Uri>();
    }

    public boolean ismAndroidBeamAvailable() {
        return mAndroidBeamAvailable;
    }

    @Override
    public Uri[] createBeamUris(NfcEvent nfcEvent) {
        return outbox.toArray(new Uri[outbox.size()]);
    }

    public void addFile(File file) {
        addUri(Uri.fromFile(file));
    }

    public void addUri(Uri uri) {
        outbox.add(uri);
    }

}
