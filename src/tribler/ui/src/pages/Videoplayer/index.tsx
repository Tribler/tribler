import {useLocation, useNavigate, useParams} from "react-router-dom";
import {useEffect, useRef, useState} from "react";
import {Popover, PopoverContent, PopoverTrigger} from "@/components/ui/popover";
import {Button} from "@/components/ui/button";
import {Command, CommandEmpty, CommandGroup, CommandInput, CommandItem, CommandList} from "@/components/ui/command";
import {Check, ChevronLeft, ChevronsUpDown, Loader2} from "lucide-react";
import {cn, getCookie, getStreamableFiles} from "@/lib/utils";
import {File} from "@/models/file.model";
import {MediaMetadata} from "@/models/mediametadata.model";
import {usePrevious} from "@/hooks/usePrevious";
import {triblerService} from "@/services/tribler.service";
import {isErrorDict} from "@/services/reporting";
import {TranscodePlayer} from "./TranscodePlayer";
import {DirectPlayer} from "./DirectPlayer";

export interface SupportedCodecs {
    video: string[];
    audio: string[];
}

interface MimeType {
    id: string;
    mime: string;
}

const VIDEO_CODECS: MimeType[] = [
    {id: "h264", mime: 'video/mp4; codecs="avc1.640028"'},
    {id: "hevc", mime: 'video/mp4; codecs="hvc1.1.6.L120.90"'},
    {id: "av1", mime: 'video/mp4; codecs="av01.0.05M.08"'},
    {id: "vp9", mime: 'video/webm; codecs="vp9"'},
];

const AUDIO_CODECS: MimeType[] = [
    {id: "aac", mime: 'audio/mp4; codecs="mp4a.40.2"'},
    {id: "opus", mime: 'audio/webm; codecs="opus"'},
    {id: "flac", mime: 'audio/mp4; codecs="flac"'},
    {id: "vorbis", mime: 'audio/ogg; codecs="vorbis"'},
    {id: "ac3", mime: 'audio/mp4; codecs="ac-3"'},
    {id: "eac3", mime: 'audio/mp4; codecs="ec-3"'},
];

export default function VideoPlayer() {
    const navigate = useNavigate();
    const location = useLocation();
    const {infohash, file: fileString} = useParams<{infohash: string; file: string}>();
    const file = fileString ? Number(fileString) : undefined;

    const prevInfohash = usePrevious(infohash);

    const [open, setOpen] = useState(false);
    const [videoFiles, setVideoFiles] = useState<File[]>([]);
    const [metadata, setMetadata] = useState<MediaMetadata | null>(null);
    const [loading, setLoading] = useState(true);

    const cachedCodecsRef = useRef<SupportedCodecs | null>(null);
    const selectedFile = videoFiles.find((f) => f.index === file);

    const getSupportedCodecs = (): SupportedCodecs => {
        if (cachedCodecsRef.current) return cachedCodecsRef.current;
        const el = document.createElement("video");
        return (cachedCodecsRef.current = {
            video: VIDEO_CODECS.filter(({mime}) => el.canPlayType(mime) !== "").map(({id}) => id),
            audio: AUDIO_CODECS.filter(({mime}) => el.canPlayType(mime) !== "").map(({id}) => id),
        });
    };

    useEffect(() => {
        if (!infohash) return setVideoFiles([]);
        if (prevInfohash !== infohash) {
            triblerService.getDownloadFiles(infohash).then((res) => {
                setVideoFiles(
                    res && !isErrorDict(res) ? getStreamableFiles(res).sort((a, b) => a.name.localeCompare(b.name)) : []
                );
            });
        }
    }, [infohash]);

    useEffect(() => {
        if (infohash && file === undefined && videoFiles.length > 0) {
            navigate(`/stream/${infohash}/${videoFiles[0].index}`, {replace: true, state: location.state});
        }
    }, [infohash, file, videoFiles, navigate]);

    useEffect(() => {
        if (!infohash || file === undefined || !selectedFile) return;

        let active = true;
        setLoading(true);
        setMetadata(null);

        const fetchMetadata = async () => {
            try {
                const codecs = getSupportedCodecs();
                const params = new URLSearchParams({
                    video_codecs: codecs.video.join(","),
                    audio_codecs: codecs.audio.join(","),
                    key: getCookie("api_key") || "",
                });
                const res = await fetch(`/api/downloads/${infohash}/metadata/${file}?${params}`, {method: "GET"});
                res.json;

                if (active) {
                    setMetadata(await res.json());
                }
            } catch {
                if (active) setMetadata(null);
            } finally {
                if (active) setLoading(false);
            }
        };

        fetchMetadata();
        return () => {
            active = false;
        };
    }, [infohash, file, selectedFile]);

    const codecs = getSupportedCodecs();
    const canDirectPlay = Boolean(
        metadata &&
            ["mp4", "mov", "webm"].some((c) => metadata.container?.toLowerCase().includes(c)) &&
            (!metadata.has_video || codecs.video.includes(metadata.video_codec?.toLowerCase())) &&
            (!metadata.has_audio || codecs.audio.includes(metadata.audio_codec?.toLowerCase()))
    );

    return (
        <div className="w-full h-full flex flex-col overflow-hidden">
            <div className="w-full flex flex-col h-full">
                <div className="flex items-center gap-1 w-full p-4 bg-background">
                    <Button
                        variant="ghost"
                        size="icon"
                        onClick={() => navigate(-1)}
                        className="text-muted-foreground hover:text-foreground shrink-0"
                        title="Back">
                        <ChevronLeft className="h-8 w-8" />
                    </Button>
                    <Popover open={open} onOpenChange={setOpen}>
                        <PopoverTrigger asChild>
                            <Button
                                variant="outline"
                                role="combobox"
                                aria-expanded={open}
                                className="flex-1 justify-between">
                                {selectedFile ? selectedFile.name : "Select video file..."}
                                <ChevronsUpDown className="ml-2 h-4 w-4 shrink-0 opacity-50" />
                            </Button>
                        </PopoverTrigger>
                        <PopoverContent className="w-[--radix-popover-trigger-width] p-0">
                            <Command>
                                <CommandInput placeholder="Search video file..." />
                                <CommandList>
                                    <CommandEmpty>No video files found.</CommandEmpty>
                                    <CommandGroup>
                                        {videoFiles.map((videoFile) => (
                                            <CommandItem
                                                key={videoFile.index}
                                                value={videoFile.name}
                                                onSelect={(currentName) => {
                                                    const file = videoFiles.find(
                                                        (videoFile) => videoFile.name === currentName
                                                    );
                                                    console.log("Changed selected video file to " + file?.name);
                                                    navigate(`/stream/${infohash}/${videoFile.index}`);
                                                    setOpen(false);
                                                }}>
                                                <Check
                                                    className={cn(
                                                        "mr-2 h-4 w-4",
                                                        file === videoFile.index ? "opacity-100" : "opacity-0"
                                                    )}
                                                />
                                                {videoFile.name}
                                            </CommandItem>
                                        ))}
                                    </CommandGroup>
                                </CommandList>
                            </Command>
                        </PopoverContent>
                    </Popover>
                </div>

                {!infohash || file === undefined || !selectedFile ? (
                    <div className="flex items-center justify-center h-64 aspect-video bg-black text-white">
                        File is not streamable
                    </div>
                ) : loading ? (
                    <div className="flex items-center justify-center h-64 aspect-video bg-black text-white gap-2">
                        <Loader2 className="h-6 w-6 animate-spin" />
                        <span>Starting stream...</span>
                    </div>
                ) : canDirectPlay ? (
                    <DirectPlayer key={`${infohash}-${file}`} infohash={infohash} file={file} />
                ) : (
                    <TranscodePlayer key={`${infohash}-${file}`} infohash={infohash} file={file} />
                )}

                {triblerService.guiSettings.dev_mode && metadata && (
                    <div className="w-full px-4 py-1 text-xs text-muted-foreground flex flex-wrap items-center gap-x-6 gap-y-1 mt-1 opacity-70 hover:opacity-100 transition-opacity duration-200 select-none">
                        <div className="flex gap-1.5">
                            <span className="px-2 py-0.5 rounded bg-foreground/15 text-secondary-foreground font-medium uppercase">
                                {canDirectPlay ? "Direct play" : "Transcoding"}
                            </span>
                            <span className="text-neutral-500">Video:</span>
                            <span className="font-mono text-accent-foreground translate-y-[1px]">
                                {metadata.width}×{metadata.height}
                            </span>
                            <span className="text-accent-foreground">
                                {metadata.pix_fmt.includes("10")
                                    ? "10-bit"
                                    : metadata.pix_fmt.includes("12")
                                      ? "12-bit"
                                      : "8-bit"}
                            </span>
                            <span className="text-accent-foreground">@{metadata.fps.toFixed(2)}fps</span>
                            <span className="text-accent-foreground">
                                {metadata.video_codec}
                                {metadata.video_tag &&
                                    metadata.video_tag !== "unknown" &&
                                    metadata.video_tag.trim() !== "" && (
                                        <span className="text-neutral-500 font-mono text-[11px] ml-1">
                                            ({metadata.video_tag})
                                        </span>
                                    )}
                            </span>
                        </div>

                        <div className="flex gap-1.5">
                            <span className="text-neutral-500">Bitrate:</span>
                            <span className="font-mono text-accent-foreground translate-y-[1px]">
                                {metadata.video_bitrate === 0
                                    ? "VBR"
                                    : `${(metadata.video_bitrate / 1_000_000).toFixed(2)} Mbps`}
                            </span>
                        </div>

                        <div className="flex gap-1.5">
                            <span className="text-neutral-500">Audio:</span>
                            {metadata.has_audio ? (
                                <span className="text-accent-foreground">
                                    {metadata.audio_codec}
                                    {metadata.audio_tag &&
                                        metadata.audio_tag !== "unknown" &&
                                        metadata.audio_tag.trim() !== "" && (
                                            <span className="text-neutral-500 font-mono text-[11px] ml-1">
                                                ({metadata.audio_tag})
                                            </span>
                                        )}
                                    {" • "}
                                    {metadata.audio_channels}ch
                                </span>
                            ) : (
                                <span className="text-neutral-500 italic">none</span>
                            )}
                        </div>
                    </div>
                )}
            </div>
        </div>
    );
}
