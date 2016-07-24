package org.tribler.android;

import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;
import android.net.ConnectivityManager;
import android.net.NetworkInfo;
import android.widget.Toast;

public class NetworkReceiver extends BroadcastReceiver {

    public static boolean isNetworkConnected(Context ctx) {
        ConnectivityManager connectivityManager = (ConnectivityManager) ctx.getSystemService(Context.CONNECTIVITY_SERVICE);
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

    /**
     * {@inheritDoc}
     */
    @Override
    public void onReceive(Context context, Intent intent) {
        if (!isNetworkConnected(context)) {
            Toast.makeText(context, R.string.warning_lost_connection, Toast.LENGTH_LONG);
        }
    }
}