package org.tribler.android;

import android.content.Context;
import android.content.Intent;
import android.content.pm.PackageManager;
import android.content.res.Configuration;
import android.net.Uri;
import android.nfc.NfcAdapter;
import android.nfc.NfcManager;
import android.provider.Settings;
import android.support.v7.app.AlertDialog;
import android.webkit.MimeTypeMap;
import android.widget.ImageView;
import android.widget.Toast;

public class MyUtils {

    public static String getMimeType(Uri uri) {
        return getMimeType(uri.toString());
    }

    public static String getMimeType(String file) {
        String type = null;
        String extension = MimeTypeMap.getFileExtensionFromUrl(file);
        if (extension != null) {
            type = MimeTypeMap.getSingleton().getMimeTypeFromExtension(extension);
        }
        return type;
    }

    /**
     * Helper method to determine if the device has an extra-large screen. For
     * example, 10" tablets are extra-large.
     */
    public static boolean isXLargeTablet(Context context) {
        return (context.getResources().getConfiguration().screenLayout
                & Configuration.SCREENLAYOUT_SIZE_MASK) >= Configuration.SCREENLAYOUT_SIZE_XLARGE;
    }

    public static void startBeam(Uri uri, Context ctx) {
        // Check if device has nfc
        if (!ctx.getPackageManager().hasSystemFeature(PackageManager.FEATURE_NFC)) {
            NfcManager nfcManager = (NfcManager) ctx.getSystemService(Context.NFC_SERVICE);
            NfcAdapter nfcAdapter = nfcManager.getDefaultAdapter();
            assert nfcAdapter != null;

            // Check if android beam is enabled
            if (!nfcAdapter.isEnabled()) {
                Toast.makeText(ctx, R.string.action_beam_nfc_enable, Toast.LENGTH_LONG).show();
                ctx.startActivity(new Intent(Settings.ACTION_NFC_SETTINGS));
            } else if (!nfcAdapter.isNdefPushEnabled()) {
                Toast.makeText(ctx, R.string.action_beam_enable, Toast.LENGTH_LONG).show();
                ctx.startActivity(new Intent(Settings.ACTION_NFCSHARING_SETTINGS));
            }

            //nfcAdapter.setBeamPushUris(new Uri[]{uri}, ctx);

            // Show instructions
            AlertDialog.Builder builder = new AlertDialog.Builder(ctx);
            ImageView image = new ImageView(ctx);
            image.setImageResource(R.drawable.beam);
            builder.setView(image);
            AlertDialog dialog = builder.create();
            dialog.show();

        } else {
            // Use bluetooth
            Intent shareIntent = new Intent();
            shareIntent.setAction(Intent.ACTION_SEND);
            shareIntent.putExtra(Intent.EXTRA_STREAM, uri);
            shareIntent.setType(MyUtils.getMimeType(uri));
            ctx.startActivity(Intent.createChooser(shareIntent, ctx.getText(R.string.action_beam_app_chooser)));
        }
    }
}
