package org.tribler.android;

import android.content.Intent;
import android.widget.Toast;

import org.tribler.android.restapi.EventStream;
import org.tribler.android.service.NoseTestService;

public class NoseTestActivity extends MainActivity {

    protected void startService() {
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
        Toast.makeText(this, R.string.status_nosetests, Toast.LENGTH_LONG).show();
        finish();
    }

}
