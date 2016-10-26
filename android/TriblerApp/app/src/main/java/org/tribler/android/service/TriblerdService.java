package org.tribler.android.service;

import android.content.Context;
import android.content.Intent;
import android.net.wifi.WifiManager;
import android.os.IBinder;
import android.os.PowerManager;
import android.support.annotation.Nullable;

import org.kivy.android.PythonService;
import org.tribler.android.R;

public class TriblerdService extends PythonService {

    public static void start(Context ctx) {
        String argument = ctx.getFilesDir().getAbsolutePath();
        Intent intent = new Intent(ctx, TriblerdService.class);
        intent.putExtra("androidPrivate", argument);
        intent.putExtra("androidArgument", argument);
        intent.putExtra("pythonName", "TriblerdService");
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
        Intent intent = new Intent(ctx, TriblerdService.class);
        ctx.stopService(intent);
    }

    private PowerManager.WakeLock wakeLock;
    private WifiManager.WifiLock wifiLock;

    /**
     * {@inheritDoc}
     */
    @Override
    public boolean getStartForeground() {
        return true;
    }

    /**
     * {@inheritDoc}
     */
    @Override
    public void onCreate() {
        super.onCreate();

        // Keep the CPU on
        PowerManager powerManager =
                (PowerManager) getApplicationContext().getSystemService(POWER_SERVICE);
        wakeLock = powerManager.newWakeLock(PowerManager.PARTIAL_WAKE_LOCK, "Tribler");
        wakeLock.acquire();

        // Keep the Wi-Fi on
        WifiManager wifiManager =
                (WifiManager) getApplicationContext().getSystemService(Context.WIFI_SERVICE);
        wifiLock = wifiManager.createWifiLock(WifiManager.WIFI_MODE_FULL, "Tribler");
        wifiLock.acquire();
    }

    /**
     * {@inheritDoc}
     */
    @Override
    public void onDestroy() {
        wakeLock.release();
        wifiLock.release();
        super.onDestroy();
    }

    /**
     * {@inheritDoc}
     */
    @Nullable
    @Override
    public IBinder onBind(Intent intent) {
        return null;
    }
}
