package org.tribler.android;

import android.content.Context;
import android.content.DialogInterface;
import android.content.Intent;
import android.content.pm.PackageManager;
import android.content.res.Configuration;
import android.net.Uri;
import android.nfc.NfcAdapter;
import android.nfc.NfcManager;
import android.provider.Settings;
import android.support.v7.app.AlertDialog;
import android.webkit.MimeTypeMap;

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

    /**
     * Show
     *
     * @param uri
     * @param ctx
     */
    public static void nfcBeam(final Uri uri, final Context ctx) {
        // Check if device has nfc
        if (ctx.getPackageManager().hasSystemFeature(PackageManager.FEATURE_NFC)) {
            NfcManager nfcManager = (NfcManager) ctx.getSystemService(Context.NFC_SERVICE);
            NfcAdapter nfcAdapter = nfcManager.getDefaultAdapter();
            assert nfcAdapter != null;

            if (!nfcAdapter.isEnabled()) {
                // Ask user to turn on nfc and android beam
                AlertDialog.Builder dialog = new AlertDialog.Builder(ctx);
                dialog.setMessage(ctx.getText(R.string.dialog_enable_nfc_beam));
                dialog.setPositiveButton("Turn On", new DialogInterface.OnClickListener() {
                    @Override
                    public void onClick(DialogInterface dialog, int which) {
                        Intent intent = new Intent(Settings.ACTION_NFC_SETTINGS);
                        ctx.startActivity(intent);
                    }
                });
                dialog.setNegativeButton("Cancel", new DialogInterface.OnClickListener() {
                    @Override
                    public void onClick(DialogInterface dialog, int which) {
                        // Send via other means
                        send(uri, ctx);
                    }
                });
                dialog.show();
            } else if (!nfcAdapter.isNdefPushEnabled()) {
                // Ask user to turn on Android Beam
                AlertDialog.Builder dialog = new AlertDialog.Builder(ctx);
                dialog.setMessage(ctx.getText(R.string.dialog_enable_beam));
                dialog.setPositiveButton("Turn On", new DialogInterface.OnClickListener() {
                    @Override
                    public void onClick(DialogInterface dialog, int which) {
                        Intent intent = new Intent(Settings.ACTION_NFCSHARING_SETTINGS);
                        ctx.startActivity(intent);
                    }
                });
                dialog.setNegativeButton("Cancel", new DialogInterface.OnClickListener() {
                    @Override
                    public void onClick(DialogInterface dialog, int which) {
                        // Send via other means
                        send(uri, ctx);
                    }
                });
                dialog.show();
            } else {
                // Nfc and Android Beam enabled
                send(uri, ctx);
            }
        } else {
            // Send via other means
            send(uri, ctx);
        }
    }

    public static void send(Uri uri, Context ctx) {
        Intent shareIntent = new Intent();
        shareIntent.setAction(Intent.ACTION_SEND);
        shareIntent.putExtra(Intent.EXTRA_STREAM, uri);
        shareIntent.setType(MyUtils.getMimeType(uri));
        ctx.startActivity(Intent.createChooser(shareIntent, ctx.getText(R.string.action_send_app_chooser)));
    }
}
