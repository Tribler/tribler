package org.tribler.android;

import android.content.Context;
import android.content.DialogInterface;
import android.content.Intent;
import android.content.pm.PackageManager;
import android.net.Uri;
import android.nfc.NfcAdapter;
import android.nfc.NfcEvent;
import android.nfc.NfcManager;
import android.os.Bundle;
import android.provider.Settings;
import android.support.v7.app.AlertDialog;
import android.support.v7.app.AppCompatActivity;
import android.widget.ImageView;

public class BeamActivity extends AppCompatActivity {

    private NfcAdapter mNfcAdapter;

    private void initNfc() {
        // Check if device has NFC
        if (getPackageManager().hasSystemFeature(PackageManager.FEATURE_NFC)) {

            NfcManager nfcManager = (NfcManager) getSystemService(Context.NFC_SERVICE);
            mNfcAdapter = nfcManager.getDefaultAdapter();

            mNfcAdapter.setOnNdefPushCompleteCallback(new NfcAdapter.OnNdefPushCompleteCallback() {
                @Override
                public void onNdefPushComplete(NfcEvent nfcEvent) {
                    // Exit BeamActivity
                    finish();
                }
            }, this);
        }
    }

    private void initGui() {
        setContentView(R.layout.activity_beam);
    }

    /**
     * {@inheritDoc}
     */
    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);

        initNfc();
        initGui();

        handleIntent(getIntent());
    }

    /**
     * {@inheritDoc}
     */
    @Override
    protected void onResume() {
        super.onResume();

        handleIntent(getIntent());
    }

    /**
     * {@inheritDoc}
     */
    @Override
    protected void onNewIntent(Intent intent) {
        setIntent(intent);
        handleIntent(intent);
    }

    private void handleIntent(Intent intent) {
        System.out.println(intent.toString()); //DEBUG

        if (Intent.ACTION_SEND.equals(intent.getAction())) {
            // Fetch uri of file to send
            Uri uri = (Uri) intent.getParcelableExtra(Intent.EXTRA_STREAM);
            if (mNfcAdapter == null) {
                // Send via other means
                sendChooser(uri);
            } else {
                doMyBeam(uri);
            }
        }
    }

    private void doMyBeam(Uri uri) {
        // Check if NFC is enabled
        if (!mNfcAdapter.isEnabled()) {
            askUser(getText(R.string.dialog_enable_nfc_beam), Settings.ACTION_NFC_SETTINGS, uri);
        }
        // Check if Android Beam is enabled
        else if (!mNfcAdapter.isNdefPushEnabled()) {
            askUser(getText(R.string.dialog_enable_beam), Settings.ACTION_NFCSHARING_SETTINGS, uri);
        }
        // NFC and Android Beam are enabled
        else {
            mNfcAdapter.setBeamPushUris(new Uri[]{uri}, this);

            // Show instructions
            ImageView image = (ImageView) findViewById(R.id.beam_image_view);
            assert image != null;
            image.setImageResource(R.drawable.beam);
        }
    }

    private void askUser(CharSequence question, final String intentAction, final Uri uri) {
        // Ask user to turn on NFC and/or Android Beam
        AlertDialog.Builder builder = new AlertDialog.Builder(this);
        builder.setMessage(question);
        builder.setPositiveButton(getText(R.string.action_turn_on), new DialogInterface.OnClickListener() {
            @Override
            public void onClick(DialogInterface dialog, int which) {
                // Open system settings
                startActivity(new Intent(intentAction));
            }
        });
        builder.setNegativeButton(getText(R.string.action_cancel), new DialogInterface.OnClickListener() {
            @Override
            public void onClick(DialogInterface dialog, int which) {
                // Send via other means
                sendChooser(uri);
            }
        });
        AlertDialog dialog = builder.create();
        dialog.show();
    }

    private void sendChooser(Uri uri) {
        Intent intent = new Intent();
        intent.setAction(Intent.ACTION_SEND);
        intent.putExtra(Intent.EXTRA_STREAM, uri);
        intent.setType(MyUtils.getMimeType(uri));
        startActivity(Intent.createChooser(intent, getText(R.string.dialog_send_chooser)));
    }
}