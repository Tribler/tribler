package org.tribler.android.service;

import android.content.Context;
import android.content.Intent;

import org.tribler.android.R;

public class NoseTestService extends TriblerdService {

    public static void start(Context ctx) {
        String argument = ctx.getFilesDir().getAbsolutePath();
        Intent intent = new Intent(ctx, NoseTestService.class);
        intent.putExtra("androidPrivate", argument);
        intent.putExtra("androidArgument", argument);
        intent.putExtra("pythonName", "NoseTests");
        intent.putExtra("pythonHome", argument);
        intent.putExtra("pythonPath", argument + ":" + argument + "/lib");
        intent.putExtra("pythonEggCache", argument + "/.egg_cache");
        // From https://raw.githubusercontent.com/Tribler/gumby/devel/scripts/run_nosetests_for_jenkins.sh
        String NOSE_ARGS_COMMON = "--with-xunit --all-modules --traverse-namespace --cover-package=Tribler --cover-tests --cover-inclusive";
        String NOSE_ARGS = "--verbose --with-xcoverage --xcoverage-file=" + argument +
                "/coverage.xml --xunit-file=" + argument + "/nosetests.xml " + NOSE_ARGS_COMMON;
        intent.putExtra("pythonServiceArgument", NOSE_ARGS);
        intent.putExtra("serviceEntrypoint", "nosetests.py");
        intent.putExtra("serviceTitle", ctx.getString(R.string.status_nosetests));
        intent.putExtra("serviceDescription", NOSE_ARGS);
        intent.putExtra("serviceIconId", R.mipmap.ic_service);
        ctx.startService(intent);
    }

    public static void stop(Context ctx) {
        Intent intent = new Intent(ctx, NoseTestService.class);
        ctx.stopService(intent);
    }

}
