import React, {useEffect, useRef, useState} from "react";
import {getCookie} from "@/lib/utils";
import {BasePlayer} from "./BasePlayer";

interface DirectPlayerProps {
    infohash: string;
    file: number;
}

export function DirectPlayer({infohash, file}: DirectPlayerProps) {
    const videoRef = useRef<HTMLVideoElement>(null);

    const [currentTime, setCurrentTime] = useState(0);
    const [duration, setDuration] = useState(0);
    const [bufferEnd, setBufferEnd] = useState(0);

    const apiKey = getCookie("api_key") || "";
    const streamUrl = `/api/downloads/${infohash}/stream/${file}${apiKey ? `?key=${encodeURIComponent(apiKey)}` : ""}`;

    useEffect(() => {
        setCurrentTime(0);
        setBufferEnd(0);
        setDuration(0);
    }, [infohash, file]);

    const updateBuffer = (video: HTMLVideoElement) => {
        const time = video.currentTime;
        for (let i = 0; i < video.buffered.length; i++) {
            if (video.buffered.start(i) <= time && time <= video.buffered.end(i)) {
                setBufferEnd(video.buffered.end(i));
                break;
            }
        }
    };

    const handleManualSeek = (seekTime: number) => {
        const video = videoRef.current;
        if (video && Number.isFinite(seekTime)) {
            video.currentTime = seekTime;
            setCurrentTime(seekTime);
        }
    };

    const handleTimeUpdate = (e: React.SyntheticEvent<HTMLVideoElement>, isSeeking: boolean) => {
        if (isSeeking) return;

        const video = e.currentTarget;
        setCurrentTime(video.currentTime);

        if (Number.isFinite(video.duration) && video.duration > 0) {
            setDuration(video.duration);
        }

        updateBuffer(video);
    };

    return (
        <BasePlayer
            videoRef={videoRef}
            src={streamUrl}
            preload="metadata"
            currentTime={currentTime}
            duration={duration}
            bufferEnd={bufferEnd}
            onTimeChange={setCurrentTime}
            onSeek={handleManualSeek}
            onTimeUpdate={handleTimeUpdate}
            onProgress={(e) => updateBuffer(e.currentTarget)}
            onLoadedMetadata={(e) => {
                if (Number.isFinite(e.currentTarget.duration) && e.currentTarget.duration > 0) {
                    setDuration(e.currentTarget.duration);
                }
            }}
            onError={(e) => {
                const err = e.currentTarget.error;
                console.error("Video error:", err?.code, err?.message);
            }}
        />
    );
}
