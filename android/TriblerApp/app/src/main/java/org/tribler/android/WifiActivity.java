package org.tribler.android;

import android.content.Context;
import android.content.Intent;
import android.content.pm.PackageManager;
import android.net.wifi.WifiManager;
import android.net.wifi.p2p.WifiP2pManager;
import android.os.Bundle;

public class WifiActivity extends BaseActivity {

    public static final int ENABLE_WIFI_ACTIVITY_REQUEST_CODE = 501;
    public static final int ENABLE_WIFI_DIRECT_ACTIVITY_REQUEST_CODE = 502;

    private WifiManager _wifiManager;
    private WifiP2pManager _wifiP2pManager;

    private void initWifi() {
        // Check if device has Wi-Fi
        if (getPackageManager().hasSystemFeature(PackageManager.FEATURE_WIFI)) {
            _wifiManager = (WifiManager) getApplicationContext().getSystemService(Context.WIFI_SERVICE);
        }
        // Check if device has Wi-Fi Direct
        if (getPackageManager().hasSystemFeature(PackageManager.FEATURE_WIFI_DIRECT)) {
            _wifiP2pManager = (WifiP2pManager) getApplicationContext().getSystemService(Context.WIFI_P2P_SERVICE);
        }
    }

    /**
     * {@inheritDoc}
     */
    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_wifi_p2p);

        initWifi();

        handleIntent(getIntent());
    }

    /**
     * {@inheritDoc}
     */
    @Override
    protected void onDestroy() {
        super.onDestroy();
        _wifiManager = null;
        _wifiP2pManager = null;
    }

    /**
     * {@inheritDoc}
     */
    @Override
    protected void handleIntent(Intent intent) {
        //TODO
    }

}
