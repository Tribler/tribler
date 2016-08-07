package org.tribler.android;

import android.content.Context;
import android.content.Intent;
import android.content.pm.PackageManager;
import android.net.Uri;
import android.nfc.NfcAdapter;
import android.nfc.NfcManager;
import android.os.Bundle;
import android.provider.Settings;
import android.support.annotation.Nullable;
import android.support.v7.app.AlertDialog;
import android.text.TextUtils;
import android.view.Menu;
import android.view.MenuItem;
import android.widget.ImageView;

import butterknife.BindView;

public class BeamActivity extends BaseActivity {

    public static final int ENABLE_NFC_BEAM_ACTIVITY_REQUEST_CODE = 201;
    public static final int ENABLE_BEAM_ACTIVITY_REQUEST_CODE = 202;

    @BindView(R.id.img_beam_instructions)
    ImageView imageView;

    private NfcAdapter _nfcAdapter;

    private void initNfc() {
        // Check if device has NFC
        if (getPackageManager().hasSystemFeature(PackageManager.FEATURE_NFC)) {
            NfcManager nfcManager =
                    (NfcManager) getApplicationContext().getSystemService(Context.NFC_SERVICE);

            _nfcAdapter = nfcManager.getDefaultAdapter();
            _nfcAdapter.setOnNdefPushCompleteCallback(nfcEvent -> {
                // Exit BeamActivity
                finish();
            }, this);
        }
    }

    /**
     * {@inheritDoc}
     */
    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_beam);
        initNfc();
        handleIntent(getIntent());
    }

    /**
     * {@inheritDoc}
     */
    @Override
    protected void onDestroy() {
        super.onDestroy();
        _nfcAdapter = null;
    }

    /**
     * {@inheritDoc}
     */
    @Override
    public boolean onCreateOptionsMenu(Menu menu) {
        super.onCreateOptionsMenu(menu);
        // Add items to the action bar (if it is present)
        getMenuInflater().inflate(R.menu.activity_beam_menu, menu);
        return true;
    }

    public void btnBluetoothClicked(@Nullable MenuItem item) {
        // Fetch uri of file to send
        Uri uri = getIntent().getParcelableExtra(Intent.EXTRA_STREAM);
        // Send via other means
        Intent chooserIntent = MyUtils.sendChooser(uri, getText(R.string.dialog_send_chooser));
        handleIntent(chooserIntent);
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

    protected void handleIntent(Intent intent) {
        String action = intent.getAction();
        if (TextUtils.isEmpty(action)) {
            return;
        }
        switch (action) {

            case Intent.ACTION_SEND:
                // Fetch uri of file to send
                Uri uri = intent.getParcelableExtra(Intent.EXTRA_STREAM);

                if (_nfcAdapter != null) {
                    doMyBeam(uri);
                } else {
                    // Send intent to use method preferred by user
                    Intent sendIntent = MyUtils.sendIntent(uri);
                    startActivity(sendIntent);
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
        if (!_nfcAdapter.isEnabled()) {
            askUser(R.string.dialog_enable_nfc_beam, Settings.ACTION_NFC_SETTINGS);
        }
        // Check if Android Beam is enabled
        else if (!_nfcAdapter.isNdefPushEnabled()) {
            askUser(R.string.dialog_enable_beam, Settings.ACTION_NFCSHARING_SETTINGS);
        }
        // NFC and Android Beam are enabled
        else {
            _nfcAdapter.setBeamPushUris(new Uri[]{uri}, this);

            // Show instructions
            imageView.setImageResource(R.drawable.beam);
        }
    }

    private void askUser(int stringId, final String action) {
        // Ask user to turn on NFC and/or Android Beam
        AlertDialog.Builder builder = new AlertDialog.Builder(this);
        builder.setMessage(getText(stringId));
        builder.setPositiveButton(getText(R.string.action_turn_on), (dialog, which) -> {
            handleIntent(new Intent(action));
        });
        builder.setNegativeButton(getText(R.string.action_cancel), (dialog, which) -> {
            // Pretend NFC is not available
            _nfcAdapter = null;
            // Proceed with original intent
            handleIntent(getIntent());
        });
        AlertDialog dialog = builder.create();
        dialog.show();
    }
}