package org.tribler.android;

import android.content.Context;
import android.content.res.Configuration;
import android.net.Uri;
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
}
