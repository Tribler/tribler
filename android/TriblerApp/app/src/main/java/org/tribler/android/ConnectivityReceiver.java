package org.tribler.android;

import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;
import android.widget.Toast;

public class ConnectivityReceiver extends BroadcastReceiver {

    /**
     * {@inheritDoc}
     */
    @Override
    public void onReceive(Context context, Intent intent) {
        if (!MyUtils.isNetworkConnected(context)) {
            Toast.makeText(context, R.string.warning_lost_connection, Toast.LENGTH_LONG).show();
        }
    }
}