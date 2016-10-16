package org.tribler.android;

import android.content.Intent;
import android.os.Bundle;
import android.support.annotation.Nullable;
import android.text.TextUtils;
import android.view.View;

public class EditChannelActivity extends BaseActivity {

    public static final String ACTION_CREATE_CHANNEL = "org.tribler.android.channel.CREATE";
    public static final String ACTION_EDIT_CHANNEL = "org.tribler.android.channel.EDIT";

    private EditChannelFragment _fragment;

    /**
     * {@inheritDoc}
     */
    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_edit_channel);

        _fragment = (EditChannelFragment) getSupportFragmentManager().findFragmentById(R.id.fragment_edit_channel);
        _fragment.setRetainInstance(true);

        handleIntent(getIntent());
    }

    /**
     * {@inheritDoc}
     */
    @Override
    protected void onDestroy() {
        super.onDestroy();
        _fragment = null;
    }

    /**
     * {@inheritDoc}
     */
    @Override
    protected void handleIntent(Intent intent) {
        String action = intent.getAction();
        // Handle intent only once
        if (!TextUtils.isEmpty(action)) {
            intent.setAction(null);
        } else {
            return;
        }
        switch (action) {

            case ACTION_CREATE_CHANNEL:
                _fragment.createChannel();
                return;

            case ACTION_EDIT_CHANNEL:
                String dispersyCid = intent.getStringExtra(ChannelActivity.EXTRA_DISPERSY_CID);
                String name = intent.getStringExtra(ChannelActivity.EXTRA_NAME);
                String description = intent.getStringExtra(ChannelActivity.EXTRA_DESCRIPTION);
                _fragment.editChannel(dispersyCid, name, description);
                return;
        }
    }

    public void btnChannelCreateClicked(@Nullable View view) {
        _fragment.btnChannelCreateClicked();
    }

    public void btnChannelSaveClicked(@Nullable View view) {
        _fragment.btnChannelSaveClicked();
    }
}
