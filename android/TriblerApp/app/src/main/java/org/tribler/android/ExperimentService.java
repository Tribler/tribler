package org.tribler.android;

import android.content.Context;
import android.content.Intent;

import org.kivy.android.PythonService;

public class ExperimentService extends PythonService {

    public static void start(Context ctx) {
        String argument = ctx.getFilesDir().getAbsolutePath();
        Intent intent = new Intent(ctx, ExperimentService.class);
        intent.putExtra("androidPrivate", argument);
        intent.putExtra("androidArgument", argument);
        intent.putExtra("pythonName", "ExperimentMultiChainScale");
        intent.putExtra("pythonHome", argument);
        intent.putExtra("pythonPath", argument + ":" + argument + "/lib");
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

}
