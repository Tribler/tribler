import React, {RefObject, useEffect, useRef, useState} from "react";
import {Maximize, Minimize, Pause, Play, Volume1, Volume2, VolumeX} from "lucide-react";

export interface BasePlayerProps extends Omit<React.VideoHTMLAttributes<HTMLVideoElement>, "onTimeUpdate"> {
    videoRef?: RefObject<HTMLVideoElement | null>;
    currentTime: number;
    duration: number;
    bufferEnd: number;
    onTimeChange: (time: number) => void;
    onSeek: (targetSeconds: number) => void | Promise<void>;
    onTimeUpdate?: (e: React.SyntheticEvent<HTMLVideoElement>, isSeeking: boolean) => void;
}

export function BasePlayer(props: BasePlayerProps) {
    const {
        videoRef: externalVideoRef,
        currentTime,
        duration,
        bufferEnd,
        onTimeChange,
        onSeek,
        onTimeUpdate,
        ...videoProps
    } = props;

    const containerRef = useRef<HTMLDivElement>(null);
    const internalVideoRef = useRef<HTMLVideoElement>(null);
    const videoRef = externalVideoRef ?? internalVideoRef;
    const controlsTimeoutRef = useRef<NodeJS.Timeout | null>(null);

    const [isPlaying, setIsPlaying] = useState(false);
    const [isSeeking, setIsSeeking] = useState(false);
    const [isBuffering, setIsBuffering] = useState(false);
    const [isFullscreen, setIsFullscreen] = useState(false);
    const [isControlsHovered, setIsControlsHovered] = useState(false);

    const [volume, setVolume] = useState<number>(() => {
        const saved = localStorage.getItem("player_volume");
        return saved ? parseFloat(saved) : 1.0;
    });
    const [isMuted, setIsMuted] = useState<boolean>(() => {
        return localStorage.getItem("player_muted") === "true";
    });

    const formatTime = (s: number) => {
        if (!Number.isFinite(s) || s < 0) return "00:00";
        const date = new Date(s * 1000).toISOString();
        return s >= 3600 ? date.substring(11, 19) : date.substring(14, 19);
    };

    useEffect(() => {
        const video = videoRef.current;
        if (!video) return;
        video.volume = volume;
        video.muted = isMuted;
    }, [videoProps.src]);

    useEffect(() => {
        const onFullscreenChange = () => setIsFullscreen(Boolean(document.fullscreenElement));
        document.addEventListener("fullscreenchange", onFullscreenChange);
        return () => document.removeEventListener("fullscreenchange", onFullscreenChange);
    }, []);

    const togglePlay = () => {
        const video = videoRef.current;
        if (!video) return;

        if (!video.paused) {
            video.pause();
        } else {
            video.play().catch((err) => console.warn("Failed to playback video:", err));
        }
    };

    const handleVolumeChange = (newVolume: number) => {
        setVolume(newVolume);
        localStorage.setItem("player_volume", newVolume.toString());
        if (videoRef.current) {
            videoRef.current.volume = newVolume;
            if (newVolume > 0 && isMuted) {
                videoRef.current.muted = false;
                setIsMuted(false);
                localStorage.setItem("player_muted", "false");
            }
        }
    };

    const toggleMute = () => {
        const video = videoRef.current;
        if (!video) return;

        const nextMuteState = !isMuted;
        video.muted = nextMuteState;
        setIsMuted(nextMuteState);
        localStorage.setItem("player_muted", nextMuteState.toString());
    };

    const toggleFullscreen = () => {
        const container = containerRef.current;
        if (!container) return;

        if (!document.fullscreenElement) {
            container.requestFullscreen().catch((err) => {
                console.error("Failed to go fullscreen:", err);
            });
        } else {
            document.exitFullscreen();
        }
    };

return (
        <div className="bg-background w-full p-4 py-0 flex flex-col items-center select-none">
            <div
                ref={containerRef}
                onMouseMove={() => {
                    setIsControlsHovered(true);
                    if (controlsTimeoutRef.current) clearTimeout(controlsTimeoutRef.current);
                    controlsTimeoutRef.current = setTimeout(() => setIsControlsHovered(false), 2500);
                }}
                onMouseLeave={() => {
                    setIsControlsHovered(false);
                    if (controlsTimeoutRef.current) clearTimeout(controlsTimeoutRef.current);
                }}
                className="fullscreen:overflow-visible relative w-full aspect-video rounded-lg overflow-hidden group border border-neutral-800 shadow-xl bg-black">
                <video
                    {...videoProps}
                    ref={videoRef}
                    onPlay={() => setIsPlaying(true)}
                    onPause={() => setIsPlaying(false)}
                    onWaiting={() => setIsBuffering(true)}
                    onPlaying={() => setIsBuffering(false)}
                    onCanPlay={() => setIsBuffering(false)}
                    onTimeUpdate={(e) => onTimeUpdate?.(e, isSeeking)}
                    onClick={togglePlay}
                    className="w-full h-full object-contain"
                    autoPlay
                />

                {isBuffering && (
                    <div className="absolute inset-0 flex items-center justify-center bg-black/40 backdrop-blur-[1px] pointer-events-none">
                        <div className="w-12 h-12 border-4 border-zinc-700 border-t-tribler rounded-full animate-spin" />
                    </div>
                )}

                <div
                    className={`absolute bottom-0 left-0 right-0 p-4 bg-gradient-to-t from-black/90 via-black/40 to-transparent z-50 transition-opacity duration-200 flex flex-col gap-3
                                ${isControlsHovered ? "opacity-100" : "opacity-0"}`}>
                    <div className="flex items-center gap-3 w-full">
                        <div className="relative flex-1 h-3 flex items-center group/timeline">
                            <div className="absolute top-1/2 -translate-y-1/2 left-0 right-0 h-1 bg-zinc-700 rounded-lg pointer-events-none" />
                            <div
                                className="absolute top-1/2 -translate-y-1/2 left-0 h-1 bg-white/30 rounded-lg pointer-events-none transition-all duration-100"
                                style={{
                                    width: `${duration ? (bufferEnd / duration) * 100 : 0}%`,
                                }}
                            />
                            <div
                                className="absolute top-1/2 -translate-y-1/2 left-0 h-1 bg-tribler rounded-lg pointer-events-none"
                                style={{
                                    width: `${duration ? (currentTime / duration) * 100 : 0}%`,
                                }}
                            />
                            <input
                                type="range"
                                min={0}
                                max={duration || 100}
                                step={0.1}
                                value={currentTime}
                                onMouseDown={() => setIsSeeking(true)}
                                onChange={(e) => onTimeChange(parseFloat(e.target.value))}
                                onMouseUp={(e) => {
                                    setIsSeeking(false);
                                    onSeek(parseFloat((e.target as HTMLInputElement).value));
                                }}
                                className="absolute inset-0 w-full h-full appearance-none bg-transparent cursor-pointer outline-none
                                            [&::-webkit-slider-thumb]:appearance-none
                                            [&::-webkit-slider-thumb]:bg-tribler
                                            [&::-webkit-slider-thumb]:h-3 [&::-webkit-slider-thumb]:w-3
                                            [&::-webkit-slider-thumb]:rounded-full
                                            [&::-moz-range-thumb]:bg-tribler
                                            [&::-moz-range-thumb]:h-3 [&::-moz-range-thumb]:w-3
                                            [&::-moz-range-thumb]:rounded-full"
                            />
                        </div>
                    </div>

                    <div className="flex items-center justify-between w-full">
                        <div className="flex items-center gap-6">
                            <button onClick={togglePlay} className="hover:text-tribler text-white transition-colors">
                                {isPlaying ? <Pause /> : <Play />}
                            </button>

                            <div className="flex items-center gap-2 group/vol">
                                <button onClick={toggleMute} className="hover:text-tribler text-white transition-colors">
                                    {isMuted || volume === 0 ? <VolumeX /> : volume < 0.5 ? <Volume1 /> : <Volume2 />}
                                </button>

                                <input
                                    type="range"
                                    min="0"
                                    max="1"
                                    step="0.05"
                                    value={isMuted ? 0 : volume}
                                    onChange={(e) => handleVolumeChange(parseFloat(e.target.value))}
                                    className="w-20 h-1 bg-zinc-600 rounded-lg appearance-none cursor-pointer accent-tribler
                                                [&::-webkit-slider-thumb]:appearance-none
                                                [&::-webkit-slider-thumb]:bg-tribler
                                                [&::-webkit-slider-thumb]:h-3 [&::-webkit-slider-thumb]:w-3
                                                [&::-webkit-slider-thumb]:rounded-full
                                                [&::-moz-range-thumb]:bg-tribler
                                                [&::-moz-range-thumb]:h-3 [&::-moz-range-thumb]:w-3
                                                [&::-moz-range-thumb]:rounded-full"
                                />
                            </div>

                            <span className="text-sm text-white font-sans tabular-nums whitespace-nowrap min-w-[100px] text-left">
                                {formatTime(currentTime)} / {formatTime(duration)}
                            </span>
                        </div>

                        <button onClick={toggleFullscreen} className="hover:text-tribler text-white transition-colors p-1">
                            {isFullscreen ? <Minimize /> : <Maximize />}
                        </button>
                    </div>
                </div>
            </div>
        </div>
    );
}
