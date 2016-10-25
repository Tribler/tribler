package org.tribler.android;

import android.content.Intent;
import android.os.Bundle;
import android.support.v7.app.ActionBar;
import android.text.TextUtils;
import android.util.Log;
import android.view.View;
import android.widget.EditText;
import android.widget.ImageView;
import android.widget.TextView;

import com.jakewharton.rxbinding.widget.RxTextView;
import com.jakewharton.rxbinding.widget.TextViewTextChangeEvent;

import butterknife.BindView;
import mehdi.sakout.fancybuttons.FancyButton;
import rx.Observer;

public class EditChannelActivity extends BaseActivity {

    public static final String ACTION_CREATE_CHANNEL = "org.tribler.android.channel.CREATE";
    public static final String ACTION_EDIT_CHANNEL = "org.tribler.android.channel.EDIT";

    @BindView(R.id.channel_icon_wrapper)
    View iconWrapper;

    @BindView(R.id.channel_icon)
    ImageView icon;

    @BindView(R.id.channel_capital)
    TextView nameCapital;

    @BindView(R.id.channel_explanation)
    TextView explanation;

    @BindView(R.id.channel_name_input)
    EditText nameInput;

    @BindView(R.id.channel_description_input)
    EditText descriptionInput;

    @BindView(R.id.btn_channel_save)
    FancyButton btnSave;

    /**
     * {@inheritDoc}
     */
    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_edit_channel);

        // Update interface while typing
        rxSubs.add(RxTextView.textChangeEvents(nameInput).subscribe(new Observer<TextViewTextChangeEvent>() {

            public void onNext(TextViewTextChangeEvent event) {
                CharSequence name = event.text();

                // Prevent submitting empty channel name or the original name
                if (TextUtils.isEmpty(name) || name.equals(getIntent().getStringExtra(ChannelActivity.EXTRA_NAME))) {
                    btnSave.setEnabled(false);
                    btnSave.setAlpha(0.2f);
                } else {
                    btnSave.setEnabled(true);
                    btnSave.setAlpha(1f);
                }

                // Update icon view
                nameCapital.setText(MyUtils.getCapitals(name, 2));
            }

            public void onCompleted() {
            }

            public void onError(Throwable e) {
                Log.e("onViewCreated", "textChangeEvents", e);
            }
        }));

        handleIntent(getIntent());
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
                btnSave.setText(getString(R.string.action_CREATE));
                explanation.setVisibility(View.VISIBLE);

                // Set title
                ActionBar actionBar = getSupportActionBar();
                if (actionBar != null) {
                    actionBar.setTitle(R.string.action_create_channel);
                }
                return;

            case ACTION_EDIT_CHANNEL:
                String dispersyCid = intent.getStringExtra(ChannelActivity.EXTRA_DISPERSY_CID);
                String name = intent.getStringExtra(ChannelActivity.EXTRA_NAME);
                String description = intent.getStringExtra(ChannelActivity.EXTRA_DESCRIPTION);

                nameCapital.setText(MyUtils.getCapitals(name, 2));
                nameInput.setText(name);
                descriptionInput.setText(description);

                int color = MyUtils.getColor(dispersyCid.hashCode());
                MyUtils.setCicleBackground(icon, color);
                iconWrapper.setVisibility(View.VISIBLE);
                return;
        }
    }

    public void btnChannelSaveClicked(View view) {
        btnSave.setEnabled(false);

        // Disable input
        nameInput.setEnabled(false);
        descriptionInput.setEnabled(false);

        String name = nameInput.getText().toString();
        String description = descriptionInput.getText().toString();

        Intent result = new Intent();
        result.putExtra(ChannelActivity.EXTRA_NAME, name);
        result.putExtra(ChannelActivity.EXTRA_DESCRIPTION, description);

        // Flag modification
        setResult(RESULT_FIRST_USER, result);
        finish();
    }

}
