package org.tribler.android;

import android.content.Context;
import android.content.Intent;

import org.kivy.android.PythonService;

import java.io.File;

public class NoseTestService extends PythonService {

    public static void start(Context ctx) {
        String argument = ctx.getFilesDir().getAbsolutePath();
        Intent intent = new Intent(ctx, NoseTestService.class);
        intent.putExtra("androidPrivate", argument);
        intent.putExtra("androidArgument", argument);
        intent.putExtra("pythonName", "NoseTests");
        intent.putExtra("pythonHome", argument);
        intent.putExtra("pythonPath", argument + ":" + argument + "/lib");
        // Clean output dir
        File dir = new File(argument, "../output");
        dir.mkdirs();
        String OUTPUT_DIR = dir.getAbsolutePath();
        // From https://raw.githubusercontent.com/Tribler/gumby/devel/scripts/run_nosetests_for_jenkins.sh
        String NOSE_ARGS_COMMON = "--with-xunit --all-modules --traverse-namespace --cover-package=Tribler --cover-tests --cover-inclusive";
        String NOSE_ARGS = "--verbose --with-xcoverage --xcoverage-file=" + OUTPUT_DIR +
                "/coverage.xml --xunit-file=" + OUTPUT_DIR + "/nosetests.xml " + NOSE_ARGS_COMMON;
        intent.putExtra("pythonServiceArgument", NOSE_ARGS);
        intent.putExtra("serviceEntrypoint", "nosetests.py");
        intent.putExtra("serviceTitle", "Tribler testing service");
        intent.putExtra("serviceDescription", "Running all tests");
        intent.putExtra("serviceIconId", R.mipmap.ic_service);
        ctx.startService(intent);
    }

    public static void stop(Context ctx) {
        Intent intent = new Intent(ctx, NoseTestService.class);
        ctx.stopService(intent);
    }

}
