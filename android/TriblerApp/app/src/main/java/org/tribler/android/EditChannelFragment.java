package org.tribler.android;

import android.app.Activity;
import android.content.Context;
import android.content.Intent;
import android.os.Bundle;
import android.support.annotation.Nullable;
import android.text.TextUtils;
import android.util.Log;
import android.view.LayoutInflater;
import android.view.View;
import android.view.ViewGroup;
import android.widget.EditText;
import android.widget.ImageView;
import android.widget.TextView;

import com.jakewharton.rxbinding.widget.RxTextView;
import com.jakewharton.rxbinding.widget.TextViewTextChangeEvent;

import org.tribler.android.restapi.json.AddedChannelAck;
import org.tribler.android.restapi.json.ModifiedAck;

import butterknife.BindView;
import mehdi.sakout.fancybuttons.FancyButton;
import rx.Observer;
import rx.android.schedulers.AndroidSchedulers;
import rx.schedulers.Schedulers;

public class EditChannelFragment extends ViewFragment {

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

    @BindView(R.id.btn_channel_create)
    FancyButton btnCreate;

    @BindView(R.id.btn_channel_save)
    FancyButton btnSave;

    @BindView(R.id.channel_progress)
    View progressView;

    @BindView(R.id.channel_progress_status)
    TextView statusBar;

    private Intent _result;

    private Intent getResult() {
        return _result;
    }

    private void setResult(Intent result) {
        _result = result;
        // result can be set while activity is not attached
        if (result != null && isAdded()) {
            Activity activity = getActivity();
            activity.setResult(Activity.RESULT_FIRST_USER, result);
            activity.finish();
        }
    }

    /**
     * {@inheritDoc}
     */
    @Override
    public void onAttach(Context context) {
        super.onAttach(context);
        // Side effects:
        setResult(getResult());
    }

    /**
     * {@inheritDoc}
     */
    @Override
    public View onCreateView(LayoutInflater inflater, @Nullable ViewGroup container, @Nullable Bundle savedInstanceState) {
        return inflater.inflate(R.layout.fragment_edit_channel, container, false);
    }

    /**
     * {@inheritDoc}
     */
    @Override
    public void onViewCreated(View view, @Nullable Bundle savedInstanceState) {
        super.onViewCreated(view, savedInstanceState);
        RxTextView.textChangeEvents(nameInput)
                .subscribe(new Observer<TextViewTextChangeEvent>() {

                    public void onNext(TextViewTextChangeEvent event) {
                        CharSequence name = event.text();
                        // Prevent submitting empty channel name
                        boolean enabled = !TextUtils.isEmpty(name);
                        btnCreate.setEnabled(enabled);
                        btnSave.setEnabled(enabled);

                        // Update icon view
                        nameCapital.setText(MyUtils.getCapitals(name, 2));
                    }

                    public void onCompleted() {
                    }

                    public void onError(Throwable e) {
                        Log.e("onViewCreated", "textChangeEvents", e);
                    }
                });
    }

    void createChannel() {
        explanation.setVisibility(View.VISIBLE);
        btnCreate.setVisibility(View.VISIBLE);
    }

    void editChannel(String dispersyCid, String name, String description) {
        int color = MyUtils.getColor(dispersyCid.hashCode());
        nameCapital.setText(MyUtils.getCapitals(name, 2));
        nameInput.setText(name);
        descriptionInput.setText(description);
        MyUtils.setCicleBackground(icon, color);
        iconWrapper.setVisibility(View.VISIBLE);
        btnSave.setVisibility(View.VISIBLE);
    }

    private void setInputEnabled(boolean enabled) {
        // Hide buttons
        btnCreate.setVisibility(enabled ? View.VISIBLE : View.GONE);
        btnSave.setVisibility(enabled ? View.VISIBLE : View.GONE);

        // Lock input fields
        btnSave.setEnabled(enabled);
        nameInput.setEnabled(enabled);
        descriptionInput.setEnabled(enabled);

        // Show loading indicator
        progressView.setVisibility(enabled ? View.GONE : View.VISIBLE);
    }

    void btnChannelCreateClicked() {
        setInputEnabled(false);
        statusBar.setText(getText(R.string.status_creating_channel));

        final String name = nameInput.getText().toString();
        final String description = descriptionInput.getText().toString();

        rxSubs.add(service.createChannel(name, description)
                .subscribeOn(Schedulers.io())
                .observeOn(AndroidSchedulers.mainThread())
                .subscribe(new Observer<AddedChannelAck>() {

                    public void onNext(AddedChannelAck ack) {
                        Log.d("createChannel", "channel_id = " + ack.getAdded());
                    }

                    public void onCompleted() {
                        Intent intent = new Intent();
                        intent.putExtra(ChannelActivity.EXTRA_NAME, name);
                        intent.putExtra(ChannelActivity.EXTRA_DESCRIPTION, description);
                        setResult(intent);
                    }

                    public void onError(Throwable e) {
                        Log.e("btnChannelCreateClicked", "createChannel", e);
                        MyUtils.onError(e, context);
                        try {
                            Thread.sleep(1000);
                        } catch (InterruptedException ex) {
                        }
                        // Retry
                        btnChannelCreateClicked();
                    }
                }));
    }

    void btnChannelSaveClicked() {
        setInputEnabled(false);
        statusBar.setText(getText(R.string.status_saving_changes));

        final String name = nameInput.getText().toString();
        final String description = descriptionInput.getText().toString();

        rxSubs.add(service.editMyChannel(name, description)
                .subscribeOn(Schedulers.io())
                .observeOn(AndroidSchedulers.mainThread())
                .subscribe(new Observer<ModifiedAck>() {

                    public void onNext(ModifiedAck ack) {
                        if (ack.isModified()) {
                            Intent intent = new Intent();
                            intent.putExtra(ChannelActivity.EXTRA_NAME, name);
                            intent.putExtra(ChannelActivity.EXTRA_DESCRIPTION, description);
                            setResult(intent);
                        }
                    }

                    public void onCompleted() {
                    }

                    public void onError(Throwable e) {
                        Log.e("btnChannelSaveClicked", "editMyChannel", e);
                        MyUtils.onError(e, context);
                        try {
                            Thread.sleep(1000);
                        } catch (InterruptedException ex) {
                        }
                        // Retry
                        btnChannelSaveClicked();
                    }
                }));
    }
}
