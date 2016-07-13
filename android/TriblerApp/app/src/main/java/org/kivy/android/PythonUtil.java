package org.kivy.android;

import android.util.Log;

import java.io.File;

public class PythonUtil {
    private static String TAG = PythonUtil.class.getSimpleName();

    protected static String[] getLibraries() {
        return new String[]{
                "/../lib/libgnustl_shared.so",
                "/../lib/libboost_system.so",
                "/../lib/libboost_date_time.so",
                "/../lib/libboost_python.so",
                "/../lib/libffi.so",
                "/../lib/libsqlite3.so",
                "/../lib/libcrypto.so",
                "/../lib/libssl.so",
                "/../lib/libsodium.so",
                "/../lib/libtorrent_rasterbar.so",

                "python2.7",
                "main",
                "/lib/python2.7/lib-dynload/_io.so",
                "/lib/python2.7/lib-dynload/unicodedata.so",
                "/lib/python2.7/lib-dynload/_ctypes.so",

                "/lib/python2.7/lib-dynload/_csv.so",
                "/lib/python2.7/lib-dynload/future_builtins.so",
                "/lib/python2.7/lib-dynload/_lsprof.so",
                "/lib/python2.7/lib-dynload/_sqlite3.so",
                "/lib/python2.7/lib-dynload/syslog.so",

                "/lib/python2.7/site-packages/_cffi_backend.so",
                "/lib/python2.7/site-packages/apsw.so",
                "/lib/python2.7/site-packages/leveldb.so",
                "/lib/python2.7/site-packages/libtorrent.so",

                "/lib/python2.7/site-packages/cryptography/hazmat/bindings/_openssl.so",
                "/lib/python2.7/site-packages/cryptography/hazmat/bindings/_constant_time.so",
                "/lib/python2.7/site-packages/cryptography/hazmat/bindings/_padding.so",

                "/lib/python2.7/site-packages/twisted/test/raiser.so",
                "/lib/python2.7/site-packages/twisted/python/_sendmsg.so",
                "/lib/python2.7/site-packages/PIL/_imaging.so",
                "/lib/python2.7/site-packages/PIL/_imagingmath.so",
                "/lib/python2.7/site-packages/Crypto/Util/strxor.so",
                "/lib/python2.7/site-packages/Crypto/Util/_counter.so",
                "/lib/python2.7/site-packages/Crypto/Hash/_SHA384.so",
                "/lib/python2.7/site-packages/Crypto/Hash/_SHA512.so",
                "/lib/python2.7/site-packages/Crypto/Hash/_MD2.so",
                "/lib/python2.7/site-packages/Crypto/Hash/_MD4.so",
                "/lib/python2.7/site-packages/Crypto/Hash/_RIPEMD160.so",
                "/lib/python2.7/site-packages/Crypto/Hash/_SHA224.so",
                "/lib/python2.7/site-packages/Crypto/Hash/_SHA256.so",
                "/lib/python2.7/site-packages/Crypto/Cipher/_XOR.so",
                "/lib/python2.7/site-packages/Crypto/Cipher/_DES3.so",
                "/lib/python2.7/site-packages/Crypto/Cipher/_DES.so",
                "/lib/python2.7/site-packages/Crypto/Cipher/_Blowfish.so",
                "/lib/python2.7/site-packages/Crypto/Cipher/_ARC2.so",
                "/lib/python2.7/site-packages/Crypto/Cipher/_ARC4.so",
                "/lib/python2.7/site-packages/Crypto/Cipher/_AES.so",
                "/lib/python2.7/site-packages/Crypto/Cipher/_CAST.so",
        };
    }

    public static void loadLibraries(File filesDir) {
        String filesDirPath = filesDir.getAbsolutePath();
        Log.v(TAG, "Loading libraries from " + filesDirPath);

        for (String lib : getLibraries()) {
            if (lib.startsWith("/")) {
                System.load(filesDirPath + lib);
            } else {
                System.loadLibrary(lib);
            }
        }

        Log.v(TAG, "Loaded everything!");
    }
}
