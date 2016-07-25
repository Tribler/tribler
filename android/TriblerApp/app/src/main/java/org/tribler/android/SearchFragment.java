package org.tribler.android;

import android.os.Bundle;
import android.support.annotation.Nullable;
import android.support.v7.widget.SearchView;
import android.text.TextUtils;
import android.util.Log;
import android.view.View;

import com.jakewharton.rxbinding.support.v7.widget.RxSearchView;

import org.tribler.android.restapi.json.QueriedAck;

import java.util.concurrent.TimeUnit;

import butterknife.BindView;
import rx.Observer;
import rx.android.schedulers.AndroidSchedulers;
import rx.schedulers.Schedulers;

public class SearchFragment extends DefaultInteractionListFragment {
    public static final String TAG = DiscoveredFragment.class.getSimpleName();

    @BindView(R.id.btn_search)
    SearchView searchView;

    public void startSearch(String query) {
        adapter.clear();

        subscriptions.add(service.startSearch(query)
                .subscribeOn(Schedulers.io())
                .observeOn(AndroidSchedulers.mainThread())
                .subscribe(new Observer<QueriedAck>() {

                    public void onNext(QueriedAck response) {
                    }

                    public void onCompleted() {
                    }

                    public void onError(Throwable e) {
                        Log.e(TAG, "startSearch", e);
                    }
                }));
    }

    /**
     * {@inheritDoc}
     */
    @Override
    public void onViewCreated(View view, @Nullable Bundle savedInstanceState) {
        super.onViewCreated(view, savedInstanceState);

        RxSearchView.queryTextChangeEvents(searchView)
                .subscribeOn(Schedulers.computation())
                .observeOn(AndroidSchedulers.mainThread())
                .debounce(400, TimeUnit.MILLISECONDS)
                .map(event -> searchView.getQuery())
                .filter(TextUtils::isEmpty)
                .doOnNext(query -> startSearch(query.toString()));
    }
}
