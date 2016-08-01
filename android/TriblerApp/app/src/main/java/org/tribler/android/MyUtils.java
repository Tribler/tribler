package org.tribler.android;

import android.app.Application;
import android.content.Context;
import android.content.Intent;
import android.content.res.Configuration;
import android.graphics.Color;
import android.net.ConnectivityManager;
import android.net.NetworkInfo;
import android.net.Uri;
import android.os.Environment;
import android.provider.MediaStore;
import android.webkit.MimeTypeMap;

import com.squareup.leakcanary.LeakCanary;
import com.squareup.leakcanary.RefWatcher;

import java.io.File;
import java.io.IOException;
import java.text.DecimalFormat;
import java.text.SimpleDateFormat;
import java.util.Date;

import okio.BufferedSource;
import rx.Observable;
import rx.Subscriber;

public class MyUtils {

    /**
     * Static class
     */
    private MyUtils() {
    }

    private static RefWatcher _refWatcher;

    public static RefWatcher getRefWatcher(Context ctx) {
        if (_refWatcher == null) {
            Application app = (Application) ctx.getApplicationContext();
            _refWatcher = LeakCanary.install(app);
        }
        return _refWatcher;
    }

    /**
     * Helper method to determine if the device has an extra-large screen. For
     * example, 10" tablets are extra-large.
     */
    public static boolean isXLargeTablet(Context context) {
        return (context.getResources().getConfiguration().screenLayout
                & Configuration.SCREENLAYOUT_SIZE_MASK) >= Configuration.SCREENLAYOUT_SIZE_XLARGE;
    }

    public static String getMimeType(Uri uri) {
        String type = null;
        String extension = MimeTypeMap.getFileExtensionFromUrl(uri.toString());
        if (extension != null) {
            type = MimeTypeMap.getSingleton().getMimeTypeFromExtension(extension);
        }
        return type;
    }

    public static Intent viewIntent(Uri uri) {
        return new Intent(Intent.ACTION_VIEW, uri);
    }

    public static Intent viewChooser(Uri uri, CharSequence title) {
        Intent intent = viewIntent(uri);
        return Intent.createChooser(intent, title);
    }

    public static Intent sendBeam(Uri uri, Context ctx) {
        Intent intent = new Intent(ctx, BeamActivity.class);
        intent.setAction(Intent.ACTION_SEND);
        intent.putExtra(Intent.EXTRA_STREAM, uri);
        intent.setType(getMimeType(uri));
        return intent;
    }

    public static Intent sendIntent(Uri uri) {
        Intent intent = new Intent();
        intent.setAction(Intent.ACTION_SEND);
        intent.putExtra(Intent.EXTRA_STREAM, uri);
        intent.setType(getMimeType(uri));
        return intent;
    }

    public static Intent sendChooser(Uri uri, CharSequence title) {
        Intent intent = sendIntent(uri);
        return Intent.createChooser(intent, title);
    }

    public static Intent captureVideo(Uri output) {
        Intent intent = new Intent(MediaStore.ACTION_VIDEO_CAPTURE);
        intent.putExtra(MediaStore.EXTRA_OUTPUT, output);
        intent.putExtra(MediaStore.EXTRA_VIDEO_QUALITY, 1); // 0: low 1: high
        return intent;
    }

    /**
     * @return The file created for saving a video
     */
    public static File getOutputVideoFile(Context ctx) throws IOException {
        File videoDir;
        if (Environment.MEDIA_MOUNTED.equals(Environment.getExternalStorageState())) {
            videoDir = new File(Environment.getExternalStoragePublicDirectory(
                    Environment.DIRECTORY_MOVIES).getAbsolutePath());
        } else {
            videoDir = new File(ctx.getFilesDir(), Environment.DIRECTORY_MOVIES);
        }
        // Create the storage directory if it does not exist
        if (!videoDir.exists() && !videoDir.mkdirs()) {
            throw new IOException(String.format("Failed to create directory: %s", videoDir));
        } else if (!videoDir.isDirectory()) {
            throw new IOException(String.format("Not a directory: %s", videoDir));
        }
        // Create a media file name
        String timeStamp = new SimpleDateFormat("yyyy-MM-dd_HH_mm_ss").format(new Date());
        return new File(videoDir, "VID_" + timeStamp + ".mp4");
    }

    public static boolean isNetworkConnected(ConnectivityManager connectivityManager) {
        NetworkInfo networkInfo = connectivityManager.getActiveNetworkInfo();
        if (networkInfo == null) {
            // No connection
            return false;
        }
        switch (networkInfo.getType()) {
            case ConnectivityManager.TYPE_ETHERNET:
            case ConnectivityManager.TYPE_WIFI:
                return true;
            case ConnectivityManager.TYPE_BLUETOOTH:
            case ConnectivityManager.TYPE_DUMMY:
            case ConnectivityManager.TYPE_MOBILE:
            case ConnectivityManager.TYPE_MOBILE_DUN:
            case ConnectivityManager.TYPE_VPN:
            case ConnectivityManager.TYPE_WIMAX:
            default:
                return false;
        }
    }

    public static String formatFileSize(long size) {
        if (size <= 0) {
            return "";
        }
        final String[] units = new String[]{"B", "kB", "MB", "GB", "TB"};
        int digitGroups = (int) (Math.log10(size) / Math.log10(1024));
        return new DecimalFormat("#,##0.#").format(size / Math.pow(1024, digitGroups)) + " " + units[digitGroups];
    }

    public static int getColor(int hashCode) throws Exception {
        int r = (hashCode & 0xFF0000) >> 16;
        int g = (hashCode & 0x00FF00) >> 8;
        int b = hashCode & 0x0000FF;
        return Color.rgb(r, g, b);
    }

    public static String getCapitals(CharSequence sequence, int amount) {
        StringBuilder builder = new StringBuilder();
        for (int i = 0, l = sequence.length(); i < l && builder.length() < amount; i++) {
            char c = sequence.charAt(i);
            if (Character.isUpperCase(c)) {
                builder.append(c);
            }
        }
        return builder.toString();
    }

    public static Observable<String> readUtf8LineByLine(BufferedSource source) {
        return Observable.create(new Observable.OnSubscribe<String>() {

            public void call(Subscriber<? super String> subscriber) {
                try {
                    while (!source.exhausted()) {
                        subscriber.onNext(source.readUtf8Line());
                    }
                } catch (IOException ex) {
                    subscriber.onError(ex);
                }
                subscriber.onCompleted();
            }
        });
    }
}
