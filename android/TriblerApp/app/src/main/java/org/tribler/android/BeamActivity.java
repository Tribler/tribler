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

    public static final int ENABLE_NFC_BEAM_ACTIVITY_REQUEST_CODE = 400;
    public static final int ENABLE_BEAM_ACTIVITY_REQUEST_CODE = 800;

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
    protected void onNewIntent(Intent intent) {
        super.onNewIntent(intent);
        setIntent(intent);
        handleIntent(intent);
    }

    /**
     * {@inheritDoc}
     */
    @Override
    protected void onActivityResult(int requestCode, int resultCode, Intent data) {
        super.onActivityResult(requestCode, resultCode, data);
        if (requestCode == ENABLE_NFC_BEAM_ACTIVITY_REQUEST_CODE || requestCode == ENABLE_BEAM_ACTIVITY_REQUEST_CODE) {
            // Proceed with original intent
            handleIntent(getIntent());
        }
    }

    private void handleIntent(Intent intent) {
        String action = intent.getAction();
        if (action == null)
            return;
        switch (action) {

            case Intent.ACTION_SEND:
                // Fetch uri of file to send
                Uri uri = (Uri) intent.getParcelableExtra(Intent.EXTRA_STREAM);

                if (mNfcAdapter != null) {
                    doMyBeam(uri);
                } else {
                    // Send via other means
                    Intent chooserIntent = MyUtils.sendChooser(uri, getText(R.string.dialog_send_chooser));
                    handleIntent(chooserIntent);
                }
                return;

            case Intent.ACTION_CHOOSER:
                // Show system settings
                startActivity(intent);
                // Exit BeamActivity
                finish();
                return;

            case Settings.ACTION_NFC_SETTINGS:
                // Open system settings
                startActivityForResult(intent, ENABLE_NFC_BEAM_ACTIVITY_REQUEST_CODE);
                return;

            case Settings.ACTION_NFCSHARING_SETTINGS:
                // Open system settings
                startActivityForResult(intent, ENABLE_BEAM_ACTIVITY_REQUEST_CODE);
                return;
        }
    }

    private void doMyBeam(Uri uri) {
        // Check if NFC is enabled
        if (!mNfcAdapter.isEnabled()) {
            askUser(R.string.dialog_enable_nfc_beam, Settings.ACTION_NFC_SETTINGS);
        }
        // Check if Android Beam is enabled
        else if (!mNfcAdapter.isNdefPushEnabled()) {
            askUser(R.string.dialog_enable_beam, Settings.ACTION_NFCSHARING_SETTINGS);
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

    private void askUser(int stringId, final String action) {
        // Ask user to turn on NFC and/or Android Beam
        AlertDialog.Builder builder = new AlertDialog.Builder(this);
        builder.setMessage(getText(stringId));
        builder.setPositiveButton(getText(R.string.action_turn_on), new DialogInterface.OnClickListener() {
            @Override
            public void onClick(DialogInterface dialog, int which) {
                handleIntent(new Intent(action));
            }
        });
        builder.setNegativeButton(getText(R.string.action_cancel), new DialogInterface.OnClickListener() {
            @Override
            public void onClick(DialogInterface dialog, int which) {
                // Pretend NFC is not available
                mNfcAdapter = null;
                // Proceed with original intent
                handleIntent(getIntent());
            }
        });
        AlertDialog dialog = builder.create();
        dialog.show();
    }
}