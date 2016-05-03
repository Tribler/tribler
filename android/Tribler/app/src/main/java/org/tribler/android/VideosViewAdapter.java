package org.tribler.android;

import android.support.v7.widget.RecyclerView;
import android.view.LayoutInflater;
import android.view.View;
import android.view.ViewGroup;
import android.widget.TextView;

import java.util.List;

public class VideosViewAdapter extends RecyclerView.Adapter<VideosViewAdapter.MyViewHolder> {

    private List<Video> moviesList;

    public class MyViewHolder extends RecyclerView.ViewHolder {
        public TextView title, description, duration;

        public MyViewHolder(View view) {
            super(view);
            title = (TextView) view.findViewById(R.id.title);
            description = (TextView) view.findViewById(R.id.description);
            duration = (TextView) view.findViewById(R.id.duration);
        }
    }


    public VideosViewAdapter(List<Video> moviesList) {
        this.moviesList = moviesList;
    }

    @Override
    public MyViewHolder onCreateViewHolder(ViewGroup parent, int viewType) {
        View itemView = LayoutInflater.from(parent.getContext())
                .inflate(R.layout.list_item_video, parent, false);

        return new MyViewHolder(itemView);
    }

    @Override
    public void onBindViewHolder(MyViewHolder holder, int position) {
        Video video = moviesList.get(position);
        holder.title.setText(video.getTitle());
        holder.description.setText(video.getDescription());
        holder.duration.setText(video.getDuration());
    }

    @Override
    public int getItemCount() {
        return moviesList.size();
    }
}