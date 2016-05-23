package org.tribler.android;

import java.io.File;
import java.util.ArrayList;
import java.util.List;

import android.app.Activity;
import android.net.Uri;
import android.nfc.NfcAdapter;
import android.nfc.NfcEvent;

public class NfcBeamListener implements NfcAdapter.CreateBeamUrisCallback {

    private List<Uri> mOutbox;
    private NfcAdapter mNfcAdapter;

    public NfcBeamListener(Activity activity) {
        mOutbox = new ArrayList<Uri>();
        mNfcAdapter = NfcAdapter.getDefaultAdapter(activity);
        mNfcAdapter.setBeamPushUrisCallback(this, activity);
    }

    /**
     * {@inheritDoc}
     */
    @Override
    public Uri[] createBeamUris(NfcEvent nfcEvent) {
        return mOutbox.toArray(new Uri[mOutbox.size()]);
    }

    public void addFile(File file) {
        addUri(Uri.fromFile(file));
    }

    public void addUri(Uri uri) {
        mOutbox.add(uri);
    }

}
