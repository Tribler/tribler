package org.tribler.android;

import android.Manifest;
import android.app.Activity;
import android.content.Intent;
import android.content.pm.PackageManager;
import android.net.Uri;
import android.nfc.NdefRecord;
import android.os.Bundle;
import android.support.annotation.NonNull;
import android.support.v4.app.ActivityCompat;
import android.support.v4.content.ContextCompat;
import android.support.v7.app.ActionBar;
import android.support.v7.app.AlertDialog;
import android.support.v7.app.AppCompatActivity;
import android.support.v7.widget.SearchView;
import android.text.InputType;
import android.text.TextUtils;
import android.util.Log;
import android.view.Menu;
import android.view.MenuInflater;
import android.view.MenuItem;
import android.widget.EditText;
import android.widget.Toast;

import com.jakewharton.rxbinding.support.v7.widget.RxSearchView;
import com.jakewharton.rxbinding.support.v7.widget.SearchViewQueryTextEvent;

import org.kivy.android.AssetExtract;
import org.tribler.android.restapi.json.AddedAck;
import org.tribler.android.restapi.json.AddedChannelAck;
import org.tribler.android.restapi.json.AddedUrlAck;
import org.tribler.android.restapi.json.ChannelOverview;
import org.tribler.android.restapi.json.ModifiedAck;
import org.tribler.android.restapi.json.MyChannelResponse;
import org.tribler.android.restapi.json.RemovedAck;
import org.tribler.android.restapi.json.TorrentCreatedResponse;
import org.tribler.android.restapi.json.TriblerTorrent;

import java.io.File;
import java.io.IOException;

import retrofit2.adapter.rxjava.HttpException;
import rx.Observable;
import rx.Observer;
import rx.android.schedulers.AndroidSchedulers;
import rx.schedulers.Schedulers;

public class MyChannelFragment extends DefaultInteractionListFragment {

    public static final int CREATE_CHANNEL_ACTIVITY_REQUEST_CODE = 401;
    public static final int EDIT_CHANNEL_ACTIVITY_REQUEST_CODE = 402;
    public static final int BROWSE_FILE_ACTIVITY_REQUEST_CODE = 411;

    public static final int READ_STORAGE_PERMISSION_REQUEST_CODE = 410;

    private String _dispersyCid;
    private String _name;
    private String _description;

    /**
     * {@inheritDoc}
     */
    @Override
    public void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setHasOptionsMenu(true);
        loadMyChannel();
    }

    /**
     * {@inheritDoc}
     */
    @Override
    public void onCreateOptionsMenu(Menu menu, MenuInflater inflater) {
        super.onCreateOptionsMenu(menu, inflater);
        // Add items to the action bar (if it is present)
        inflater.inflate(R.menu.fragment_my_channel_menu, menu);

        // Hide main search button
        menu.findItem(R.id.btn_search).setShowAsActionFlags(MenuItem.SHOW_AS_ACTION_NEVER);

        // Search button
        MenuItem btnFilter = menu.findItem(R.id.btn_filter_my_channel);
        SearchView searchView = (SearchView) btnFilter.getActionView();

        // Set search hint
        searchView.setQueryHint(getText(R.string.action_search_in_channel));

        // Filter on query text change
        rxMenuSubs.add(RxSearchView.queryTextChangeEvents(searchView)
                .subscribe(new Observer<SearchViewQueryTextEvent>() {

                    public void onNext(SearchViewQueryTextEvent event) {
                        adapter.getFilter().filter(event.queryText());
                    }

                    public void onCompleted() {
                    }

                    public void onError(Throwable e) {
                        Log.e("onCreateOptionsMenu", "queryTextChangeEvents", e);
                    }
                }));
    }

    /**
     * {@inheritDoc}
     */
    @Override
    public void onPrepareOptionsMenu(Menu menu) {
        super.onPrepareOptionsMenu(menu);

        // Is my channel created?
        boolean created = (_dispersyCid != null);
        menu.findItem(R.id.btn_add_my_channel).setVisible(created);
        menu.findItem(R.id.btn_beam_my_channel).setVisible(created);
        menu.findItem(R.id.btn_edit_my_channel).setVisible(created);
        menu.findItem(R.id.btn_filter_my_channel).setVisible(created);

        // Set title
        if (context instanceof AppCompatActivity) {
            ActionBar actionBar = ((AppCompatActivity) context).getSupportActionBar();
            if (actionBar != null) {
                if (_name != null) {
                    actionBar.setTitle(_name);
                } else {
                    actionBar.setTitle(R.string.action_my_channel);
                }
            }
        }
    }

    /**
     * {@inheritDoc}
     */
    @Override
    public void reload() {
        super.reload();
        loadMyChannelTorrents();
    }

    /**
     * {@inheritDoc}
     */
    @Override
    public void onSwipedRight(final TriblerTorrent torrent) {
        // Revert swipe
        adapter.notifyObjectChanged(torrent);
    }

    /**
     * {@inheritDoc}
     */
    @Override
    public void onSwipedLeft(final TriblerTorrent torrent) {
        askUserToDeleteTorrent(torrent);
    }

    private void createMyChannel() {
        showLoading(R.string.status_creating_channel);

        rxSubs.add(service.createChannel(_name, _description)
                .subscribeOn(Schedulers.io())
                .retryWhen(MyUtils::twoSecondsDelay)
                .observeOn(AndroidSchedulers.mainThread())
                .subscribe(new Observer<AddedChannelAck>() {

                    public void onNext(AddedChannelAck response) {
                        Log.d("createChannel", "channel_id = " + response.getAdded());
                        // Added?
                        if (response.getAdded() > 0) {
                            loadMyChannel();
                        } else {
                            throw new Error("Channel not added");
                        }
                    }

                    public void onCompleted() {
                    }

                    public void onError(Throwable e) {
                        MyUtils.onError(MyChannelFragment.this, "createChannel", e);
                    }
                }));
    }

    private void editMyChannel() {
        rxSubs.add(service.editMyChannel(_name, _description)
                .subscribeOn(Schedulers.io())
                .retryWhen(MyUtils::twoSecondsDelay)
                .observeOn(AndroidSchedulers.mainThread())
                .subscribe(new Observer<ModifiedAck>() {

                    public void onNext(ModifiedAck response) {
                        Log.d("editMyChannel", "modified = " + String.valueOf(response.isModified()));
                        // Modified?
                        if (!response.isModified()) {
                            throw new Error("Channel not modified");
                        }
                    }

                    public void onCompleted() {
                    }

                    public void onError(Throwable e) {
                        MyUtils.onError(MyChannelFragment.this, "editMyChannel", e);
                    }
                }));
    }

    private void loadMyChannel() {
        showLoading(true);

        rxSubs.add(service.getMyChannel()
                .subscribeOn(Schedulers.io())
                .retryWhen(MyUtils::twoSecondsDelay)
                .map(MyChannelResponse::getMyChannel)
                .observeOn(AndroidSchedulers.mainThread())
                .subscribe(new Observer<ChannelOverview>() {

                    public void onNext(ChannelOverview overview) {
                        _dispersyCid = overview.getIdentifier();
                        _name = overview.getName();
                        _description = overview.getDescription();
                        // Update view
                        invalidateOptionsMenu();
                    }

                    public void onCompleted() {
                        loadMyChannelTorrents();
                    }

                    public void onError(Throwable e) {
                        if (e instanceof HttpException && ((HttpException) e).code() == 404) {
                            // My channel has not been created yet
                            createChannel();
                            showLoading(false);
                        } else {
                            MyUtils.onError(MyChannelFragment.this, "getMyChannel", e);
                        }
                    }
                }));
    }

    private void loadMyChannelTorrents() {
        rxSubs.add(service.getTorrents(_dispersyCid, 1)
                .subscribeOn(Schedulers.io())
                .retryWhen(MyUtils::twoSecondsDelay)
                .flatMap(response -> Observable.from(response.getTorrents()))
                .observeOn(AndroidSchedulers.mainThread())
                .subscribe(new Observer<TriblerTorrent>() {

                    public void onNext(TriblerTorrent torrent) {
                        if (torrent.getInfohash() != null && torrent.getSize() > 0) {
                            adapter.addObject(torrent);
                        } else {
                            Log.v("MyChannelTorrent", String.format("%s size: %d (%s)", torrent.getName(), torrent.getSize(), torrent.getInfohash()));
                        }
                    }

                    public void onCompleted() {
                        showLoading(false);
                    }

                    public void onError(Throwable e) {
                        MyUtils.onError(MyChannelFragment.this, "getTorrents", e);
                    }
                }));
    }

    private void createTorrent(final File file, final boolean delete) {
        Log.v("createTorrent", file.getAbsolutePath());

        rxSubs.add(service.createTorrent(new String[]{file.getAbsolutePath()})
                .subscribeOn(Schedulers.io())
                .retryWhen(MyUtils::twoSecondsDelay)
                .observeOn(AndroidSchedulers.mainThread())
                .subscribe(new Observer<TorrentCreatedResponse>() {

                    public void onNext(TorrentCreatedResponse response) {
                        Log.v("createTorrent", String.format(context.getString(R.string.info_created_success), "Torrent"));

                        Toast.makeText(context, String.format(context.getString(R.string.info_created_success), "Torrent"), Toast.LENGTH_SHORT).show();
                        // Add to my channel immediately
                        addTorrent(response.getTorrent());
                    }

                    public void onCompleted() {
                        if (delete) {
                            AssetExtract.recursiveDelete(new File(file.getParent()));
                        }
                    }

                    public void onError(Throwable e) {
                        if (e instanceof HttpException && ((HttpException) e).code() == 500) {
                            // Torrent has not been created
                            String question = String.format(context.getString(R.string.info_created_failure), "torrent");
                            askUser(question, R.string.action_RETRY, v -> askUserToAddTorrent());
                        } else {
                            MyUtils.onError(MyChannelFragment.this, "createTorrent", e);
                        }
                    }
                }));
    }

    private void addTorrent(final String torrent_b64) {
        adapter.clear();
        showLoading(R.string.status_adding_torrent);

        rxSubs.add(service.addTorrent(_dispersyCid, torrent_b64)
                .subscribeOn(Schedulers.io())
                .retryWhen(MyUtils::twoSecondsDelay)
                .observeOn(AndroidSchedulers.mainThread())
                .subscribe(new Observer<AddedAck>() {

                    public void onNext(AddedAck response) {
                        // Added?
                        if (response.isAdded()) {
                            Log.v("addTorrent", String.format(context.getString(R.string.info_added_success), "Torrent"));

                            Toast.makeText(context, String.format(context.getString(R.string.info_added_success), "Torrent"), Toast.LENGTH_SHORT).show();
                        } else {
                            throw new Error("Torrent not added");
                        }
                    }

                    public void onCompleted() {
                        // Update view
                        reload();
                    }

                    public void onError(Throwable e) {
                        onCompleted();

                        if (e instanceof HttpException && ((HttpException) e).code() == 500) {
                            String error = null;
                            try {
                                error = ((HttpException) e).response().errorBody().string();
                            } catch (IOException e1) {
                                e1.printStackTrace();
                            }
                            if ("{\"error\": {\"message\": null, \"code\": \"DuplicateTorrentFileError\", \"handled\": true}}".equals(error)) {
                                Toast.makeText(context, String.format(context.getString(R.string.info_added_already), "Torrent"), Toast.LENGTH_SHORT).show();
                            } else {
                                // Torrent has not been added
                                String question = String.format(context.getString(R.string.info_added_failure), "torrent");
                                askUser(question, R.string.action_RETRY, v -> askUserToAddTorrent());
                            }
                        } else {
                            MyUtils.onError(MyChannelFragment.this, "addTorrent64", e);
                        }
                    }
                }));
    }

    private void addTorrent(final Uri url) {
        adapter.clear();
        showLoading(R.string.status_adding_torrent);

        rxSubs.add(service.addTorrent(_dispersyCid, url)
                .subscribeOn(Schedulers.io())
                .retryWhen(MyUtils::twoSecondsDelay)
                .observeOn(AndroidSchedulers.mainThread())
                .subscribe(new Observer<AddedUrlAck>() {

                    public void onNext(AddedUrlAck response) {
                        // Added?
                        if (url.equals(response.getAdded())) {
                            Log.v("addTorrentUrl", String.format(context.getString(R.string.info_added_success), "Url"));

                            Toast.makeText(context, String.format(context.getString(R.string.info_added_success), "Url"), Toast.LENGTH_SHORT).show();
                        } else {
                            throw new Error(String.format("Torrent url not added: %s != %s", url.toString(), response.getAdded()));
                        }
                    }

                    public void onCompleted() {
                        // Update view
                        reload();
                    }

                    public void onError(Throwable e) {
                        onCompleted();

                        if (e instanceof HttpException && ((HttpException) e).code() == 500) {
                            String error = null;
                            try {
                                error = ((HttpException) e).response().errorBody().string();
                            } catch (IOException e1) {
                                e1.printStackTrace();
                            }
                            if ("{\"error\": {\"message\": null, \"code\": \"DuplicateTorrentFileError\", \"handled\": true}}".equals(error)) {
                                Toast.makeText(context, String.format(context.getString(R.string.info_added_already), "Url"), Toast.LENGTH_SHORT).show();
                            } else {
                                // Torrent has not been added
                                String question = String.format(context.getString(R.string.info_added_failure), "url");
                                askUser(question, R.string.action_RETRY, v -> askUserToAddTorrent());
                            }
                        } else {
                            MyUtils.onError(MyChannelFragment.this, "addTorrentUrl", e);
                        }
                    }
                }));
    }

    private void deleteTorrent(final String infohash, final String name) {
        rxSubs.add(service.deleteTorrent(_dispersyCid, infohash)
                .subscribeOn(Schedulers.io())
                .retryWhen(MyUtils::twoSecondsDelay)
                .observeOn(AndroidSchedulers.mainThread())
                .subscribe(new Observer<RemovedAck>() {

                    public void onNext(RemovedAck response) {
                        // Removed?
                        if (response.isRemoved()) {
                            Toast.makeText(context, String.format(context.getString(R.string.info_removed_success), name), Toast.LENGTH_SHORT).show();
                        } else {
                            throw new Error(String.format("Torrent not removed: %s \"%s\"", infohash, name));
                        }
                    }

                    public void onCompleted() {
                    }

                    public void onError(Throwable e) {
                        if (e instanceof HttpException && ((HttpException) e).code() == 404) {
                            // Torrent was already deleted
                            Toast.makeText(context, String.format(context.getString(R.string.info_removed_already), name), Toast.LENGTH_SHORT).show();
                        } else {
                            MyUtils.onError(MyChannelFragment.this, "deleteTorrent", e);
                        }
                    }
                }));
    }

    private void askUserToCreateMyChannel() {
        AlertDialog.Builder builder = new AlertDialog.Builder(context);
        builder.setMessage(R.string.dialog_create_my_channel);
        builder.setPositiveButton(R.string.action_create, (dialog, which) -> {
            createChannel();
        });
        builder.setNegativeButton(R.string.action_cancel, (dialog, which) -> {
            // Do nothing
        });
        AlertDialog dialog = builder.create();
        dialog.show();
    }

    void askUserToAddTorrent() {
        AlertDialog.Builder builder = new AlertDialog.Builder(context);
        builder.setMessage(R.string.dialog_add_torrent);

        EditText input = new EditText(context);
        input.setInputType(InputType.TYPE_CLASS_TEXT | InputType.TYPE_TEXT_VARIATION_URI);
        input.setHint(R.string.hint_add_torrent);
        builder.setView(input);

        builder.setPositiveButton(R.string.action_add, (dialog, which) -> {
            CharSequence text = input.getText();
            if (!TextUtils.isEmpty(text)) {
                Uri uri = Uri.parse(text.toString());
                addTorrent(uri);
            }
        });
        builder.setNeutralButton(R.string.action_browse, (dialog, which) -> {
            // Browse file to create torrent
            askUserToSelectFile();
        });
        builder.setNegativeButton(R.string.action_cancel, (dialog, which) -> {
            // Do nothing
        });
        AlertDialog dialog = builder.create();
        dialog.show();
    }

    private void askUserToDeleteTorrent(TriblerTorrent torrent) {
        AlertDialog.Builder builder = new AlertDialog.Builder(context);
        builder.setMessage(String.format(getString(R.string.dialog_delete_torrent), torrent.getName()));
        builder.setPositiveButton(R.string.action_delete, (dialog, which) -> {
            adapter.removeObject(torrent);
            deleteTorrent(torrent.getInfohash(), torrent.getName());
        });
        builder.setNegativeButton(R.string.action_cancel, (dialog, which) -> {
            // Revert swipe
            adapter.notifyObjectChanged(torrent);
        });
        AlertDialog dialog = builder.create();
        dialog.show();
    }

    void askUserToBeamChannelId() {
        NdefRecord record = NdefRecord.createMime("text/plain", _dispersyCid.getBytes());
        Intent beamIntent = MyUtils.beamIntent(record);
        startActivity(beamIntent);
    }

    private void askUserToSelectFile() {
        if (ContextCompat.checkSelfPermission(getActivity(), Manifest.permission.READ_EXTERNAL_STORAGE) != PackageManager.PERMISSION_GRANTED) {
            ActivityCompat.requestPermissions(getActivity(), new String[]{Manifest.permission.READ_EXTERNAL_STORAGE}, READ_STORAGE_PERMISSION_REQUEST_CODE);
        } else {
            Intent browseIntent = MyUtils.browseFileIntent();
            Intent chooserIntent = Intent.createChooser(browseIntent, getText(R.string.dialog_create_torrent));
            startActivityForResult(chooserIntent, BROWSE_FILE_ACTIVITY_REQUEST_CODE);
        }
    }

    private void createChannel() {
        Intent createIntent = MyUtils.createChannelIntent();
        startActivityForResult(createIntent, CREATE_CHANNEL_ACTIVITY_REQUEST_CODE);
    }

    void editChannel() {
        Intent editIntent = MyUtils.editChannelIntent(_dispersyCid, _name, _description);
        startActivityForResult(editIntent, EDIT_CHANNEL_ACTIVITY_REQUEST_CODE);
    }

    /**
     * {@inheritDoc}
     */
    @Override
    public void onRequestPermissionsResult(int requestCode, @NonNull String[] permissions, @NonNull int[] grantResults) {
        super.onRequestPermissionsResult(requestCode, permissions, grantResults);
        switch (requestCode) {

            case READ_STORAGE_PERMISSION_REQUEST_CODE:
                // If request is cancelled, the result arrays are empty
                if (grantResults.length > 0 && grantResults[0] == PackageManager.PERMISSION_GRANTED) {
                    askUserToSelectFile();
                }
                return;
        }
    }

    /**
     * {@inheritDoc}
     */
    @Override
    public void onActivityResult(int requestCode, int resultCode, Intent data) {
        switch (requestCode) {

            case CREATE_CHANNEL_ACTIVITY_REQUEST_CODE:
                switch (resultCode) {

                    case Activity.RESULT_FIRST_USER:
                        _name = data.getStringExtra(ChannelActivity.EXTRA_NAME);
                        _description = data.getStringExtra(ChannelActivity.EXTRA_DESCRIPTION);
                        // Update view
                        invalidateOptionsMenu();

                        createMyChannel();
                        return;

                    case Activity.RESULT_CANCELED:
                        askUserToCreateMyChannel();
                        return;
                }
                return;

            case EDIT_CHANNEL_ACTIVITY_REQUEST_CODE:
                switch (resultCode) {

                    case Activity.RESULT_FIRST_USER:
                        _name = data.getStringExtra(ChannelActivity.EXTRA_NAME);
                        _description = data.getStringExtra(ChannelActivity.EXTRA_DESCRIPTION);
                        // Update view
                        invalidateOptionsMenu();

                        editMyChannel();
                        return;

                    case Activity.RESULT_CANCELED:
                        // Do nothing
                        return;
                }
                return;

            case BROWSE_FILE_ACTIVITY_REQUEST_CODE:
                switch (resultCode) {

                    case Activity.RESULT_OK:
                        adapter.clear();
                        showLoading(R.string.status_creating_torrent);

                        rxSubs.add(Observable.fromCallable(() -> MyUtils.resolveUri(data.getData(), context))
                                .subscribeOn(Schedulers.io())
                                .observeOn(AndroidSchedulers.mainThread())
                                .subscribe(new Observer<File>() {

                                    public void onNext(File file) {
                                        createTorrent(file, true);
                                    }

                                    public void onCompleted() {
                                    }

                                    public void onError(Throwable e) {
                                        Log.e("askUserToSelectFile", "resolveUri", e);
                                        // Retry
                                        askUserToSelectFile();
                                    }
                                }));
                        return;

                    case Activity.RESULT_CANCELED:
                        // Do nothing
                        return;
                }
                return;
        }
    }

}
