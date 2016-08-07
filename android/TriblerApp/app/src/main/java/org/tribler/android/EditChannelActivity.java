package org.tribler.android;

import android.app.Activity;
import android.content.Intent;
import android.os.Bundle;
import android.support.annotation.Nullable;
import android.text.TextUtils;
import android.util.Log;
import android.view.View;
import android.widget.Button;
import android.widget.EditText;
import android.widget.ImageView;
import android.widget.TextView;

import org.tribler.android.restapi.IRestApi;
import org.tribler.android.restapi.TriblerService;
import org.tribler.android.restapi.json.AddedChannelAck;
import org.tribler.android.restapi.json.ModifiedAck;

import butterknife.BindView;
import rx.Observer;
import rx.android.schedulers.AndroidSchedulers;
import rx.schedulers.Schedulers;

public class EditChannelActivity extends BaseActivity {

    public static final String ACTION_CREATE_CHANNEL = "org.tribler.android.channel.CREATE";

    private IRestApi _service;

    @BindView(R.id.channel_icon_wrapper)
    View iconWrapper;

    @BindView(R.id.channel_icon)
    ImageView icon;

    @BindView(R.id.channel_capital)
    TextView nameCapital;

    @BindView(R.id.my_channel_explanation)
    TextView explanation;

    @BindView(R.id.channel_name_input)
    EditText nameInput;

    @BindView(R.id.channel_description_input)
    EditText descriptionInput;

    @BindView(R.id.btn_channel_save)
    Button btnSave;

    @BindView(R.id.channel_progress)
    View progressView;

    @BindView(R.id.channel_progress_status)
    TextView statusBar;

    /**
     * {@inheritDoc}
     */
    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_edit_channel);

        String baseUrl = getString(R.string.service_url) + ":" + getString(R.string.service_port_number);
        String authToken = getString(R.string.service_auth_token);
        _service = TriblerService.createService(baseUrl, authToken);

        handleIntent(getIntent());
    }

    @Override
    protected void onDestroy() {
        super.onDestroy();
        _service = null;
    }

    /**
     * {@inheritDoc}
     */
    @Override
    protected void handleIntent(Intent intent) {
        String action = intent.getAction();
        if (TextUtils.isEmpty(action)) {
            return;
        }
        switch (action) {

            case ACTION_CREATE_CHANNEL:
                btnSave.setText(getText(R.string.action_create));
                explanation.setVisibility(View.VISIBLE);
                return;

            case Intent.ACTION_EDIT:
                String dispersyCid = intent.getStringExtra(ChannelActivity.EXTRA_DISPERSY_CID);
                String name = intent.getStringExtra(ChannelActivity.EXTRA_NAME);
                String description = intent.getStringExtra(ChannelActivity.EXTRA_DESCRIPTION);
                int color = MyUtils.getColor(dispersyCid.hashCode());
                nameCapital.setText(MyUtils.getCapitals(name, 2));
                nameInput.setText(name);
                descriptionInput.setText(description);
                MyUtils.setCicleBackground(icon, color);
                iconWrapper.setVisibility(View.VISIBLE);
                return;
        }
    }

    public void btnChannelSaveClicked(@Nullable View view) {
        // Lock input fields
        btnSave.setEnabled(false);
        nameInput.setEnabled(false);
        descriptionInput.setEnabled(false);

        // Show loading indicator
        progressView.setVisibility(View.VISIBLE);
        btnSave.setVisibility(View.GONE);

        String name = nameInput.getText().toString();
        String description = descriptionInput.getText().toString();

        if (ACTION_CREATE_CHANNEL.equals(getIntent().getAction())) {
            statusBar.setText(getText(R.string.status_creating_channel));

            rxSubs.add(_service.createChannel(name, description)
                    .subscribeOn(Schedulers.io())
                    .observeOn(AndroidSchedulers.mainThread())
                    .subscribe(new Observer<AddedChannelAck>() {

                        public void onNext(AddedChannelAck ack) {
                        }

                        public void onCompleted() {
                            setResult(Activity.RESULT_OK);
                            finish();
                        }

                        public void onError(Throwable e) {
                            Log.e("btnChannelSaveClicked", "createChannel", e);
                            // Retry
                            btnChannelSaveClicked(null);
                        }
                    }));
        } else {

            rxSubs.add(_service.editMyChannel(name, description)
                    .subscribeOn(Schedulers.io())
                    .observeOn(AndroidSchedulers.mainThread())
                    .subscribe(new Observer<ModifiedAck>() {

                        public void onNext(ModifiedAck ack) {
                        }

                        public void onCompleted() {
                            setResult(Activity.RESULT_OK);
                            finish();
                        }

                        public void onError(Throwable e) {
                            Log.e("btnChannelSaveClicked", "editMyChannel", e);
                            // Retry
                            btnChannelSaveClicked(null);
                        }
                    }));
        }
    }
}
