package org.tribler.android;

import android.content.Intent;

import org.tribler.android.restapi.EventStream;
import org.tribler.android.service.NoseTestService;

public class NoseTestActivity extends MainActivity {

    protected void initService() {
        NoseTestService.start(this); // Run tests
    }

    protected void killService() {
        NoseTestService.stop(this);
    }

    /**
     * {@inheritDoc}
     */
    @Override
    protected void handleIntent(Intent intent) {
        EventStream.closeEventStream();
        statusBar.setText(getString(R.string.status_nosetests));
        super.handleIntent(intent);
    }

}
