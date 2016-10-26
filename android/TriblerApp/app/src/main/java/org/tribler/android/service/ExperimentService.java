package org.tribler.android.service;

import android.content.Context;
import android.content.Intent;

import com.google.gson.Gson;

import org.tribler.android.R;

import java.util.HashMap;

public class ExperimentService extends TriblerdService {

    public static void start(Context ctx, String experiment, HashMap args) {
        String json = new Gson().toJson(args);
        String argument = ctx.getFilesDir().getAbsolutePath();
        Intent intent = new Intent(ctx, ExperimentService.class);
        intent.putExtra("androidPrivate", argument);
        intent.putExtra("androidArgument", argument);
        intent.putExtra("pythonName", experiment);
        intent.putExtra("pythonHome", argument);
        intent.putExtra("pythonPath", argument + ":" + argument + "/lib");
        intent.putExtra("pythonEggCache", argument + "/.egg_cache");
        intent.putExtra("pythonServiceArgument", json);
        intent.putExtra("serviceEntrypoint", "experiment.py");
        intent.putExtra("serviceTitle", String.format(ctx.getString(R.string.status_experiment), experiment));
        intent.putExtra("serviceDescription", json);
        intent.putExtra("serviceIconId", R.mipmap.ic_service);
        ctx.startService(intent);
    }

    public static void stop(Context ctx) {
        Intent intent = new Intent(ctx, ExperimentService.class);
        ctx.stopService(intent);
    }

}
