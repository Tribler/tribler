package org.tribler.android.restapi;

import org.tribler.android.restapi.json.ChannelsResponse;
import org.tribler.android.restapi.json.QueriedAck;
import org.tribler.android.restapi.json.SubscribedAck;
import org.tribler.android.restapi.json.SubscribedChannelsResponse;
import org.tribler.android.restapi.json.TorrentsResponse;
import org.tribler.android.restapi.json.TriblerEvent;
import org.tribler.android.restapi.json.UnsubscribedAck;

import retrofit2.http.DELETE;
import retrofit2.http.GET;
import retrofit2.http.PUT;
import retrofit2.http.Path;
import rx.Observable;

public interface IRestApi {

    @GET("/events")
    Observable<TriblerEvent> getEventStream();

    @GET("/search?q={query}")
    Observable<QueriedAck> startSearch(
            @Path("query") String query
    );

    @GET("/channels/discovered")
    Observable<ChannelsResponse> getDiscoveredChannels();

    @GET("/channels/discovered/{dispersy_cid}/torrents")
    Observable<TorrentsResponse> getTorrents(
            @Path("dispersy_cid") String dispersyCid
    );

    @GET("/channels/subscribed")
    Observable<SubscribedChannelsResponse> getSubscribedChannels();

    @PUT("/channels/subscribed/{dispersy_cid}")
    Observable<SubscribedAck> subscribe(
            @Path("dispersy_cid") String dispersyCid
    );

    @DELETE("/channels/subscribed/{dispersy_cid}")
    Observable<UnsubscribedAck> unsubscribe(
            @Path("dispersy_cid") String dispersyCid
    );
}