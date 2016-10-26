package org.tribler.android.service;

import android.content.Context;
import android.content.Intent;

import org.tribler.android.R;

import java.io.File;

public class TwistdService extends TriblerdService {

    public static void start(Context ctx) {
        String argument = ctx.getFilesDir().getAbsolutePath();
        Intent intent = new Intent(ctx, TwistdService.class);
        intent.putExtra("androidPrivate", argument);
        intent.putExtra("androidArgument", argument);
        intent.putExtra("pythonName", "TwistdService");
        intent.putExtra("pythonHome", argument);
        intent.putExtra("pythonPath", argument + ":" + argument + "/lib");
        intent.putExtra("pythonEggCache", argument + "/.egg_cache");
        // Clean output dir
        File dir = new File(argument, "../output");
        dir.mkdirs();
        String OUTPUT_DIR = dir.getAbsolutePath();
        String TWISTD_ARGS = "--savestats --profile=" + OUTPUT_DIR +
                "/cprofiler.dat -n tribler -p " + ctx.getString(R.string.service_port_number);
        intent.putExtra("pythonServiceArgument", TWISTD_ARGS);
        intent.putExtra("serviceEntrypoint", "twistd.py");
        intent.putExtra("serviceTitle", "Profiling Tribler with twistd plugin");
        intent.putExtra("serviceDescription", ctx.getString(R.string.service_url) + ":"
                + ctx.getString(R.string.service_port_number));
        intent.putExtra("serviceIconId", R.mipmap.ic_service);
        ctx.startService(intent);
    }

    public static void stop(Context ctx) {
        Intent intent = new Intent(ctx, TwistdService.class);
        ctx.stopService(intent);
    }

}
