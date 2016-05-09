package org.tribler.android;

import android.webkit.MimeTypeMap;

public class MyUtils {

    public String getMimeType(String file) {
        String type = null;
        String extension = MimeTypeMap.getFileExtensionFromUrl(file);
        if (extension != null) {
            type = MimeTypeMap.getSingleton().getMimeTypeFromExtension(extension);
        }
        return type;
    }
}
