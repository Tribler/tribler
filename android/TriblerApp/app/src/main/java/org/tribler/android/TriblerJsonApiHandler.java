package org.tribler.android;

import com.google.gson.Gson;
import com.loopj.android.http.BaseJsonHttpResponseHandler;

import cz.msebera.android.httpclient.Header;

public class TriblerJsonApiHandler extends BaseJsonHttpResponseHandler<TriblerChannel> {

    private static Gson gson = new Gson();

    /**
     * {@inheritDoc}
     */
    @Override
    public void onSuccess(int statusCode, Header[] headers, String rawJsonResponse, TriblerChannel response) {

    }

    /**
     * {@inheritDoc}
     */
    @Override
    public void onFailure(int statusCode, Header[] headers, Throwable throwable, String rawJsonData, TriblerChannel errorResponse) {

    }

    /**
     * {@inheritDoc}
     */
    @Override
    protected TriblerChannel parseResponse(String rawJsonData, boolean isFailure) throws Throwable {
        return gson.fromJson(rawJsonData, TriblerChannel.class);
    }
}