import React, {useEffect, useRef, useState} from "react";
import {MediaMetadata} from "@/models/mediametadata.model";
import {getCookie} from "@/lib/utils";
import {BasePlayer} from "./BasePlayer";

const SEGMENT_SIZE = 60;

interface TranscodePlayerProps {
    infohash: string;
    file: number;
}

export function TranscodePlayer({infohash, file}: TranscodePlayerProps) {
    const videoRef = useRef<HTMLVideoElement>(null);
    const mediaSourceRef = useRef<MediaSource | null>(null);
    const sourceBufferRef = useRef<SourceBuffer | null>(null);
    const activeAbortControllerRef = useRef<AbortController | null>(null);
    const totalDurationRef = useRef<number>(0);

    const [metadata, setMetadata] = useState<MediaMetadata | null>(null);
    const [currentTime, setCurrentTime] = useState<number>(0);
    const [bufferEnd, setBufferEnd] = useState<number>(0);

    function buildStreamUrl(seconds: number): string {
        const startMs = Math.round(seconds * 1000);
        const stopMs = startMs + SEGMENT_SIZE * 1000 + 1000;
        const apiKey = getCookie("api_key") || "";

        const params = new URLSearchParams({
            start: startMs.toString(),
            stop: stopMs.toString(),
            key: apiKey,
        });

        return `/api/downloads/${infohash}/transcode/${file}?${params.toString()}`;
    }

    useEffect(() => {
        let active = true;
        const video = videoRef.current;
        if (!video) return;

        setCurrentTime(0);
        setBufferEnd(0);
        totalDurationRef.current = 0;

        const mediaSource = new MediaSource();
        mediaSourceRef.current = mediaSource;
        const objectUrl = URL.createObjectURL(mediaSource);
        video.src = objectUrl;

        const onSourceOpen = async () => {
            try {
                const response = await fetch(buildStreamUrl(0), {method: "HEAD"});
                const metadataJson = response.headers.get("X-Media-Metadata");
                if (metadataJson && active) {
                    const parsed = JSON.parse(metadataJson);
                    setMetadata(parsed);
                    totalDurationRef.current = parsed.duration ? parseFloat(parsed.duration) : 0;
                }
            } catch (err) {
                console.error("Failed to parse metadata:", err);
            }

            const codec = 'video/mp4; codecs="avc1.42E01E, mp4a.40.2"';
            if (MediaSource.isTypeSupported(codec) && active && mediaSource.readyState === "open") {
                sourceBufferRef.current = mediaSource.addSourceBuffer(codec);
                if (totalDurationRef.current > 0) {
                    mediaSource.duration = totalDurationRef.current;
                }
                startStreaming(0);
            }
        };

        mediaSource.addEventListener("sourceopen", onSourceOpen);

        return () => {
            active = false;
            activeAbortControllerRef.current?.abort();
            mediaSource.removeEventListener("sourceopen", onSourceOpen);
            URL.revokeObjectURL(objectUrl);
        };
    }, [infohash, file]);

    async function startStreaming(startOffset: number) {
        activeAbortControllerRef.current?.abort();

        const controller = new AbortController();
        activeAbortControllerRef.current = controller;

        const buffer = sourceBufferRef.current;
        if (!buffer) return;

        try {
            let currentOffset = startOffset;

            while (currentOffset < totalDurationRef.current) {
                if (controller.signal.aborted) break;

                if (buffer.buffered.length > 0) {
                    const end = buffer.buffered.end(buffer.buffered.length - 1);
                    console.log(`Setting timestampOffset to ${end}s`);
                    buffer.timestampOffset = end;
                } else {
                    buffer.timestampOffset = currentOffset;
                }

                buffer.appendWindowStart = 0;
                buffer.appendWindowEnd = Infinity;

                const response = await fetch(buildStreamUrl(currentOffset), {signal: controller.signal});
                if (!response.body || !response.ok) break;

                const reader = response.body.getReader();
                let requestComplete = false;

                while (!requestComplete) {
                    if (controller.signal.aborted) break;

                    const video = videoRef.current;
                    if (video && buffer.buffered.length > 0) {
                        const currentBufferedEnd = buffer.buffered.end(buffer.buffered.length - 1);
                        if (currentBufferedEnd - video.currentTime > 40) {
                            await new Promise((res) => setTimeout(res, 200));
                            continue;
                        }
                    }

                    const {done, value} = await reader.read();

                    if (done) {
                        const video = videoRef.current;
                        if (video && buffer.buffered.length > 0) {
                            const end = buffer.buffered.end(buffer.buffered.length - 1);
                            console.log(`Streaming request finished. Moving offset to ${end}s`);
                            currentOffset = end;
                        } else {
                            currentOffset += SEGMENT_SIZE;
                        }
                        requestComplete = true;
                        break;
                    }

                    await new Promise<void>((resolve, reject) => {
                        const appendData = () => {
                            if (controller.signal.aborted) return resolve();
                            if (!buffer.updating) {
                                try {
                                    buffer.addEventListener("updateend", () => resolve(), {once: true});
                                    buffer.appendBuffer(value);
                                } catch (err) {
                                    reject(err);
                                }
                            } else {
                                setTimeout(appendData, 10);
                            }
                        };
                        appendData();
                    });
                }

                if (controller.signal.aborted) break;
            }
        } catch (err: any) {
            if (err.name !== "AbortError") {
                console.error("Error while streaming", err);
            }
        }
    }

    const handleTimeUpdate = (e: React.SyntheticEvent<HTMLVideoElement>, isSeeking: boolean) => {
        if (isSeeking) return;

        const video = e.currentTarget;
        const time = video.currentTime;
        setCurrentTime(time);

        const ranges: string[] = [];
        let currentBufferedEnd = 0;

        for (let i = 0; i < video.buffered.length; i++) {
            const start = video.buffered.start(i);
            const end = video.buffered.end(i);
            ranges.push(`[${start.toFixed(3)}s - ${end.toFixed(3)}s]`);

            if (time >= start && time <= end) {
                currentBufferedEnd = end;
            }
        }

        if (currentBufferedEnd === 0 && video.buffered.length > 0) {
            currentBufferedEnd = video.buffered.end(0);
        }

        setBufferEnd(currentBufferedEnd);

        console.log(
            `Streaming status: ` +
                `time=${time.toFixed(3)}s, ` +
                `ready=${video.readyState}, ` +
                `paused=${video.paused}, ` +
                `ranges=${ranges.join(", ") || "[]"}`
        );
    };

    const handleManualSeek = async (targetSeconds: number) => {
        const video = videoRef.current;
        const buffer = sourceBufferRef.current;
        const mediaSource = mediaSourceRef.current;
        if (!video || !buffer || !mediaSource) return;

        for (let i = 0; i < video.buffered.length; i++) {
            if (targetSeconds >= video.buffered.start(i) && targetSeconds <= video.buffered.end(i)) {
                video.currentTime = targetSeconds;
                return;
            }
        }

        activeAbortControllerRef.current?.abort();

        if (buffer.updating) {
            await new Promise<void>((res) => buffer.addEventListener("updateend", () => res(), {once: true}));
        }

        try {
            buffer.abort();
            buffer.appendWindowStart = 0;
            buffer.appendWindowEnd = Infinity;

            if (buffer.buffered.length > 0) {
                buffer.remove(0, totalDurationRef.current || Infinity);
                await new Promise<void>((res) => buffer.addEventListener("updateend", () => res(), {once: true}));
            }

            if (totalDurationRef.current > 0) {
                mediaSource.duration = totalDurationRef.current;
            }
        } catch (e) {
            console.warn("Error while resetting buffer:", e);
        }

        video.currentTime = targetSeconds;
        setCurrentTime(targetSeconds);
        startStreaming(targetSeconds);
    };

    return (
        <BasePlayer
            videoRef={videoRef}
            currentTime={currentTime}
            duration={totalDurationRef.current}
            bufferEnd={bufferEnd}
            onTimeChange={setCurrentTime}
            onSeek={handleManualSeek}
            onTimeUpdate={handleTimeUpdate}
            onError={(e) => {
                const err = e.currentTarget.error;
                console.error("Video error:", err?.code, err?.message);
                activeAbortControllerRef.current?.abort();
            }}
        />
    );
}
