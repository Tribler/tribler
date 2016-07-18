package org.tribler.android;

import android.content.Context;
import android.content.Intent;
import android.net.wifi.WifiManager;
import android.os.PowerManager;

import org.kivy.android.PythonService;

public class Triblerd extends PythonService {
    public static final int REST_API_PORT = 8088;

    public static void start(Context ctx) {
        String argument = ctx.getFilesDir().getAbsolutePath();
        Intent intent = new Intent(ctx, Triblerd.class);
        intent.putExtra("androidPrivate", argument);
        intent.putExtra("androidArgument", argument);
        intent.putExtra("pythonName", "Triblerd");
        intent.putExtra("pythonHome", argument);
        intent.putExtra("pythonPath", argument + ":" + argument + "/lib");
        intent.putExtra("pythonEggCache", argument + "/.egg_cache");
        intent.putExtra("pythonServiceArgument", "-p " + REST_API_PORT);
        intent.putExtra("serviceEntrypoint", "triblerd.py");
        intent.putExtra("serviceTitle", "Tribler service");
        intent.putExtra("serviceDescription", "127.0.0.1:" + REST_API_PORT);
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
