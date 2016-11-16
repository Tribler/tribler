package org.tribler.android;

import android.app.Application;
import android.content.ContentResolver;
import android.content.Context;
import android.content.Intent;
import android.content.pm.PackageManager;
import android.content.res.Configuration;
import android.database.Cursor;
import android.graphics.Color;
import android.graphics.drawable.ShapeDrawable;
import android.graphics.drawable.shapes.OvalShape;
import android.net.ConnectivityManager;
import android.net.NetworkInfo;
import android.net.Uri;
import android.nfc.NdefMessage;
import android.nfc.NdefRecord;
import android.os.Bundle;
import android.os.Environment;
import android.os.Parcelable;
import android.provider.MediaStore;
import android.util.Log;
import android.webkit.MimeTypeMap;
import android.widget.ImageView;
import android.widget.Toast;

import com.squareup.leakcanary.LeakCanary;
import com.squareup.leakcanary.RefWatcher;

import java.io.File;
import java.io.FileOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.io.OutputStream;
import java.net.ConnectException;
import java.text.SimpleDateFormat;
import java.util.Arrays;
import java.util.Date;
import java.util.Random;
import java.util.concurrent.TimeUnit;

import okio.BufferedSource;
import retrofit2.adapter.rxjava.HttpException;
import rx.Observable;
import rx.Subscriber;

public class MyUtils {

    /**
     * Static class
     */
    private MyUtils() {
    }

    private static Random rand = new Random();

    private static RefWatcher _refWatcher;

    public static RefWatcher getRefWatcher(Context context) {
        if (_refWatcher == null) {
            Application app = (Application) context.getApplicationContext();
            _refWatcher = LeakCanary.install(app);
        }
        return _refWatcher;
    }

    public static String getPackageName() {
        return MyUtils.class.getPackage().getName();
    }

    public static boolean isPackageInstalled(String packageName, Context context) {
        try {
            PackageManager pm = context.getPackageManager();
            pm.getPackageInfo(packageName, PackageManager.GET_ACTIVITIES);
            return true;
        } catch (PackageManager.NameNotFoundException e) {
            return false;
        }
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

    public static Intent viewUriIntent(Uri uri) {
        return new Intent(Intent.ACTION_VIEW, uri);
    }

    public static Intent viewFileIntent(Uri file) {
        Intent intent = new Intent(Intent.ACTION_VIEW);
        intent.setDataAndType(file, getMimeType(file));
        return intent;
    }

    public static Intent viewChannelIntent(String dispersyCid, int channelId, String name, boolean subscribed) {
        Intent intent = new Intent(Intent.ACTION_GET_CONTENT);
        intent.setClassName(getPackageName(), ChannelActivity.class.getName());
        intent.putExtra(ChannelActivity.EXTRA_DISPERSY_CID, dispersyCid);
        intent.putExtra(ChannelActivity.EXTRA_CHANNEL_ID, channelId);
        intent.putExtra(ChannelActivity.EXTRA_NAME, name);
        intent.putExtra(ChannelActivity.EXTRA_SUBSCRIBED, subscribed);
        return intent;
    }

    public static Intent editChannelIntent(String dispersyCid, String name, String description) {
        Intent intent = new Intent(EditChannelActivity.ACTION_EDIT_CHANNEL);
        intent.setClassName(getPackageName(), EditChannelActivity.class.getName());
        intent.putExtra(ChannelActivity.EXTRA_DISPERSY_CID, dispersyCid);
        intent.putExtra(ChannelActivity.EXTRA_NAME, name);
        intent.putExtra(ChannelActivity.EXTRA_DESCRIPTION, description);
        return intent;
    }

    public static Intent createChannelIntent() {
        Intent intent = new Intent(EditChannelActivity.ACTION_CREATE_CHANNEL);
        intent.setClassName(getPackageName(), EditChannelActivity.class.getName());
        return intent;
    }

    public static Intent beamIntent(Uri uri) {
        Intent intent = new Intent(Intent.ACTION_SEND);
        intent.setClassName(getPackageName(), BeamActivity.class.getName());
        intent.putExtra(Intent.EXTRA_STREAM, uri);
        intent.setType(getMimeType(uri));
        return intent;
    }

    public static Intent beamIntent(NdefRecord record) {
        Intent intent = new Intent(Intent.ACTION_SEND);
        intent.setClassName(getPackageName(), BeamActivity.class.getName());
        intent.putExtra(Intent.EXTRA_STREAM, new NdefMessage(record));
        intent.setType(record.toMimeType());
        return intent;
    }

    public static Intent sendIntent(Uri uri) {
        Intent intent = new Intent(Intent.ACTION_SEND);
        intent.putExtra(Intent.EXTRA_STREAM, uri);
        intent.setType(getMimeType(uri));
        return intent;
    }

    public static Intent browseFileIntent() {
        return browseFileIntent("*/*");
    }

    public static Intent browseFileIntent(String mimeType) {
        Intent intent = new Intent(Intent.ACTION_GET_CONTENT);
        intent.addCategory(Intent.CATEGORY_OPENABLE);
        intent.setType(mimeType);
        return intent;
    }

    public static Intent captureImageIntent(Uri output) {
        Intent intent = new Intent(MediaStore.ACTION_IMAGE_CAPTURE);
        intent.putExtra(MediaStore.EXTRA_OUTPUT, output);
        return intent;
    }

    public static Intent captureVideoIntent(Uri output) {
        Intent intent = new Intent(MediaStore.ACTION_VIDEO_CAPTURE);
        intent.putExtra(MediaStore.EXTRA_OUTPUT, output);
        intent.putExtra(MediaStore.EXTRA_VIDEO_QUALITY, 1); // 0: low 1: high
        return intent;
    }

    /**
     * @return The file created for saving an image
     */
    public static File getImageOutputFile(Context context) throws IOException {
        File imageDir;
        if (Environment.MEDIA_MOUNTED.equals(Environment.getExternalStorageState())) {
            imageDir = new File(Environment.getExternalStoragePublicDirectory(
                    Environment.DIRECTORY_DCIM).getAbsolutePath());
        } else {
            imageDir = new File(context.getFilesDir(), Environment.DIRECTORY_DCIM);
        }
        // Create the storage directory if it does not exist
        if (!imageDir.exists() && !imageDir.mkdirs()) {
            throw new IOException(String.format("Failed to create directory: %s", imageDir));
        } else if (!imageDir.isDirectory()) {
            throw new IOException(String.format("Not a directory: %s", imageDir));
        }
        // Create a image file name
        String timeStamp = new SimpleDateFormat("yyyy-MM-dd_HH_mm_ss").format(new Date());
        return new File(imageDir, String.format("IMG_%s.jpg", timeStamp));
    }

    /**
     * @return The file created for saving a video
     */
    public static File getVideoOutputFile(Context context) throws IOException {
        File videoDir;
        if (Environment.MEDIA_MOUNTED.equals(Environment.getExternalStorageState())) {
            videoDir = new File(Environment.getExternalStoragePublicDirectory(
                    Environment.DIRECTORY_MOVIES).getAbsolutePath());
        } else {
            videoDir = new File(context.getFilesDir(), Environment.DIRECTORY_MOVIES);
        }
        // Create the storage directory if it does not exist
        if (!videoDir.exists() && !videoDir.mkdirs()) {
            throw new IOException(String.format("Failed to create directory: %s", videoDir));
        } else if (!videoDir.isDirectory()) {
            throw new IOException(String.format("Not a directory: %s", videoDir));
        }
        // Create a video file name
        String timeStamp = new SimpleDateFormat("yyyy-MM-dd_HH_mm_ss").format(new Date());
        return new File(videoDir, String.format("VID_%s.mp4", timeStamp));
    }

    public static void copy(InputStream input, OutputStream output) throws IOException {
        try {
            byte[] buffer = new byte[1024];
            int length;
            while ((length = input.read(buffer)) > 0) {
                output.write(buffer, 0, length);
            }
        } finally {
            try {
                input.close();
            } catch (IOException ex) {
            }
            output.close();
        }
    }

    public static String humanReadableByteCount(long bytes, boolean si) {
        int unit = si ? 1000 : 1024;
        if (bytes < unit) return bytes + " B";
        int exp = (int) (Math.log(bytes) / Math.log(unit));
        String pre = (si ? "kMGTPE" : "KMGTPE").charAt(exp - 1) + (si ? "" : "i");
        return String.format("%.1f %sB", bytes / Math.pow(unit, exp), pre);
    }

    public static int getColor(int hashCode) {
        int r = (hashCode & 0xFF0000) >> 16;
        int g = (hashCode & 0x00FF00) >> 8;
        int b = hashCode & 0x0000FF;
        return Color.rgb(r, g, b);
    }

    public static void setCicleBackground(ImageView view, int color) {
        ShapeDrawable circle = new ShapeDrawable(new OvalShape());
        circle.getPaint().setColor(color);
        circle.setBounds(0, 0, view.getWidth(), view.getHeight());
        view.setBackground(circle);
    }

    public static int randInt() {
        return randInt(0, Integer.MAX_VALUE);
    }

    /**
     * Returns a pseudo-random number between min and max, inclusive.
     * The difference between min and max can be at most
     * <code>Integer.MAX_VALUE - 1</code>.
     *
     * @param min Minimum value
     * @param max Maximum value.  Must be greater than min.
     * @return Integer between min and max, inclusive.
     * @see java.util.Random#nextInt(int)
     */
    public static int randInt(int min, int max) {
        // nextInt is normally exclusive of the top value,
        // so add 1 to make it inclusive
        return rand.nextInt((max - min) + 1) + min;
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

    public static File resolveUri(Uri uri, Context context) throws IOException {
        ContentResolver resolver = context.getContentResolver();
        String fileName = uri.getLastPathSegment();

        // Get meta-data
        Cursor cursor = resolver.query(uri, null, null, null, null);
        if (cursor != null && cursor.moveToFirst()) {
            for (int i = 0, j = cursor.getColumnCount(); i < j; i++) {
                Log.v(cursor.getColumnName(i), cursor.getString(i)); //DEBUG
            }
            try {
                int i = cursor.getColumnIndexOrThrow(MediaStore.MediaColumns.DISPLAY_NAME);
                fileName = cursor.getString(i);
            } catch (IllegalArgumentException ex) {
            }
            cursor.close();
        }

        // The name of the dir the file is in becomes the name of the .torrent file
        File dir = new File(context.getCacheDir(), fileName);
        File file = new File(dir, fileName);
        dir.mkdirs();

        // Make file accessible to service by copying to app cache dir
        InputStream input = resolver.openInputStream(uri);
        OutputStream output = new FileOutputStream(file, false);
        MyUtils.copy(input, output);
        return file;
    }

    public static File resolveAsset(String fileName, Context context) throws IOException {
        // Make file accessible by copying to external cache dir
        File file = new File(context.getExternalCacheDir(), fileName);
        InputStream input = context.getAssets().open(fileName);
        OutputStream output = new FileOutputStream(file, false);
        MyUtils.copy(input, output);
        return file;
    }

    public static String intentToString(Intent intent) {
        if (intent == null) {
            return null;
        }
        return intent.toString() + " " + bundleToString(intent.getExtras());
    }

    public static String bundleToString(Bundle bundle) {
        StringBuilder out = new StringBuilder("Bundle[");

        if (bundle == null) {
            out.append("null");
        } else {
            boolean first = true;
            for (String key : bundle.keySet()) {
                if (!first) {
                    out.append(", ");
                }
                out.append(key).append('=');
                Object value = bundle.get(key);

                if (value instanceof int[]) {
                    out.append(Arrays.toString((int[]) value));
                } else if (value instanceof byte[]) {
                    out.append(Arrays.toString((byte[]) value));
                } else if (value instanceof boolean[]) {
                    out.append(Arrays.toString((boolean[]) value));
                } else if (value instanceof short[]) {
                    out.append(Arrays.toString((short[]) value));
                } else if (value instanceof long[]) {
                    out.append(Arrays.toString((long[]) value));
                } else if (value instanceof float[]) {
                    out.append(Arrays.toString((float[]) value));
                } else if (value instanceof double[]) {
                    out.append(Arrays.toString((double[]) value));
                } else if (value instanceof String[]) {
                    out.append(Arrays.toString((String[]) value));
                } else if (value instanceof CharSequence[]) {
                    out.append(Arrays.toString((CharSequence[]) value));
                } else if (value instanceof Parcelable[]) {
                    out.append(Arrays.toString((Parcelable[]) value));
                } else if (value instanceof Bundle) {
                    out.append(bundleToString((Bundle) value));
                } else {
                    out.append(value);
                }

                first = false;
            }
        }
        out.append("]");
        return out.toString();
    }

    public static void onError(BaseFragment f, String msg, Throwable e) {
        Log.e(f.getClass().getSimpleName(), msg, e);
        Toast.makeText(f.getContext(), R.string.exception_http_500, Toast.LENGTH_SHORT).show();
        if (f instanceof ViewFragment) {
            ((ViewFragment) f).showLoading(false);
        }
    }

    public static Observable<?> twoSecondsDelay(Observable<? extends Throwable> errors) {
        return errors.flatMap(e -> {
            if (e instanceof HttpException) {
                return Observable.error(e);
            }
            if (e instanceof ConnectException) {
                Log.v("twoSecDelay", String.format("%s. %s", e.getClass().getSimpleName(), e.getMessage()));
            } else {
                Log.e("twoSecDelay", String.format("%s. %s", e.getClass().getSimpleName(), e.getMessage()), e);
            }
            // Retry
            return Observable.timer(2, TimeUnit.SECONDS);
        });
    }

}
