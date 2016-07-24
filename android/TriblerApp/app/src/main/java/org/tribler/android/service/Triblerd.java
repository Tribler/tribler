package org.tribler.android.service;

import android.content.Context;
import android.content.Intent;
import android.net.wifi.WifiManager;
import android.os.PowerManager;

import org.kivy.android.PythonService;
import org.tribler.android.R;

public class Triblerd extends PythonService {

    public static void start(Context ctx) {
        String argument = ctx.getFilesDir().getAbsolutePath();
        Intent intent = new Intent(ctx, Triblerd.class);
        intent.putExtra("androidPrivate", argument);
        intent.putExtra("androidArgument", argument);
        intent.putExtra("pythonName", "Triblerd");
        intent.putExtra("pythonHome", argument);
        intent.putExtra("pythonPath", argument + ":" + argument + "/lib");
        intent.putExtra("pythonServiceArgument", "-p " + ctx.getString(R.string.service_port_number));
        intent.putExtra("serviceEntrypoint", "triblerd.py");
        intent.putExtra("serviceTitle", "Tribler service");
        intent.putExtra("serviceDescription", ctx.getString(R.string.service_url) + ":"
                + ctx.getString(R.string.service_port_number));
        intent.putExtra("serviceIconId", R.mipmap.ic_service);
        ctx.startService(intent);
    }

    public static void stop(Context ctx) {
        Intent intent = new Intent(ctx, Triblerd.class);
        ctx.stopService(intent);
    }

    private PowerManager.WakeLock wakeLock;
    private WifiManager.WifiLock wifiLock;

    @Override
    public void onCreate() {
        // Keep the CPU on
        PowerManager powerManager = (PowerManager) getSystemService(POWER_SERVICE);
        wakeLock = powerManager.newWakeLock(PowerManager.PARTIAL_WAKE_LOCK, "Tribler");
        wakeLock.acquire();

        // Keep the Wi-Fi on
        WifiManager wifiManager = (WifiManager) getSystemService(Context.WIFI_SERVICE);
        wifiLock = wifiManager.createWifiLock(WifiManager.WIFI_MODE_FULL, "Tribler");
        wifiLock.acquire();

        super.onCreate();
    }

    @Override
    public void onDestroy() {
        wakeLock.release();
        wifiLock.release();
        super.onDestroy();
    }
}
