package org.tribler.android;

import org.tribler.android.service.TwistdService;

public class ProfilerActivity extends MainActivity {

    protected void startService() {
        TwistdService.start(this); // Run profiler
    }

    protected void killService() {
        TwistdService.stop(this);
    }
}
