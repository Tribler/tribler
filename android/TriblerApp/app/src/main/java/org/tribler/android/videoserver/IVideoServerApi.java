package org.tribler.android.videoserver;

import retrofit2.http.GET;
import retrofit2.http.Path;
import rx.Observable;

public interface IVideoServerApi {

    @GET("/{infohash}/{index}")
    Observable<VideoServerResponse> startPlaying(
            @Path("infohash") String infohash,
            @Path("index") int fileIndex
    );

}
