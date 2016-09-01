package org.tribler.android;

import org.tribler.android.service.Twistd;

public class TwistdActivity extends MainActivity {

    protected void initService() {
        Twistd.start(this); // Run profiler
    }

    protected void killService() {
        Twistd.stop(this);
    }
}
