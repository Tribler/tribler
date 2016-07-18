package org.tribler.android;

import android.content.Context;
import android.content.Intent;

import java.io.File;

public class Twistd extends Triblerd {
    public static final int REST_API_PORT = 8087;

    public static void start(Context ctx) {
        String argument = ctx.getFilesDir().getAbsolutePath();
        Intent intent = new Intent(ctx, Twistd.class);
        intent.putExtra("androidPrivate", argument);
        intent.putExtra("androidArgument", argument);
        intent.putExtra("pythonName", "Twistd");
        intent.putExtra("pythonHome", argument);
        intent.putExtra("pythonPath", argument + ":" + argument + "/lib");
        intent.putExtra("pythonEggCache", argument + "/.egg_cache");
        // Clean output dir
        File dir = new File(argument, "../output");
        dir.mkdirs();
        String OUTPUT_DIR = dir.getAbsolutePath();
        String TWISTD_ARGS = "--savestats --profile=" + OUTPUT_DIR +
                "/cprofiler.dat -n tribler -p " + REST_API_PORT;
        intent.putExtra("pythonServiceArgument", TWISTD_ARGS);
        intent.putExtra("serviceEntrypoint", "twistd.py");
        intent.putExtra("serviceTitle", "Tribler profiler");
        intent.putExtra("serviceDescription", "127.0.0.1:" + REST_API_PORT);
        intent.putExtra("serviceIconId", R.mipmap.ic_service);
        ctx.startService(intent);
    }

    public static void stop(Context ctx) {
        Intent intent = new Intent(ctx, Twistd.class);
        ctx.stopService(intent);
    }

}
