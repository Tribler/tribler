package org.tribler.android.service;

import android.content.Context;
import android.content.Intent;
import android.os.IBinder;
import android.support.annotation.Nullable;

import org.kivy.android.PythonService;
import org.tribler.android.R;

public class ExperimentService extends PythonService {

    public static void start(Context ctx) {
        String argument = ctx.getFilesDir().getAbsolutePath();
        Intent intent = new Intent(ctx, ExperimentService.class);
        intent.putExtra("androidPrivate", argument);
        intent.putExtra("androidArgument", argument);
        intent.putExtra("pythonName", "ExperimentMultiChainScale");
        intent.putExtra("pythonHome", argument);
        intent.putExtra("pythonPath", argument + ":" + argument + "/lib");
        intent.putExtra("pythonEggCache", argument + "/.egg_cache");
        intent.putExtra("pythonServiceArgument", "{'blocks_in_thousands': 10}");
        intent.putExtra("serviceEntrypoint", "experiment.py");
        intent.putExtra("serviceTitle", "Tribler experiment: MultiChainScale");
        intent.putExtra("serviceDescription", "Running with: blocks_in_thousands=10");
        intent.putExtra("serviceIconId", R.mipmap.ic_service);
        ctx.startService(intent);
    }

    public static void stop(Context ctx) {
        Intent intent = new Intent(ctx, ExperimentService.class);
        ctx.stopService(intent);
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
