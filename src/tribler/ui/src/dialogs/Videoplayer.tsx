import {DialogProps} from "@radix-ui/react-dialog";
import {Dialog, DialogContent, DialogHeader, DialogTitle} from "@/components/ui/dialog";
import React, {JSX, useEffect, useState} from "react";
import {useTranslation} from "react-i18next";
import videojs from "video.js";
import es from "video.js/dist/lang/es.json";
import hi from "video.js/dist/lang/hi.json";
import ko from "video.js/dist/lang/ko.json";
import ptBR from "video.js/dist/lang/pt-BR.json";
import ru from "video.js/dist/lang/ru.json";
import sv from "video.js/dist/lang/sv.json";
import svSupplement from "@/i18n/videojs-sv.json";
import zhCN from "video.js/dist/lang/zh-CN.json";
import "video.js/dist/video-js.css";
import {Download} from "@/models/download.model";
import {Popover, PopoverContent, PopoverTrigger} from "@/components/ui/popover";
import {Button} from "@/components/ui/button";
import {Command, CommandEmpty, CommandGroup, CommandInput, CommandItem, CommandList} from "@/components/ui/command";
import {Check, ChevronsUpDown} from "lucide-react";
import {cn, getStreamableFiles} from "@/lib/utils";
import {File} from "@/models/file.model";
import {usePrevious} from "@/hooks/usePrevious";
import {triblerService} from "@/services/tribler.service";
import {isErrorDict} from "@/services/reporting";

const playerLanguages = {es, hi, ko, "pt-BR": ptBR, ru, sv: {...sv, ...svSupplement}, "zh-CN": zhCN};

export interface VideoDialogProps extends JSX.IntrinsicAttributes, DialogProps {
    download: Download | null;
}

export function VideoDialog(props: VideoDialogProps) {
    const {t} = useTranslation();
    const [open, setOpen] = React.useState(false);
    const [selectedFile, setSelectedFile] = React.useState<File | undefined>();
    const prevDownload = usePrevious(props.download);

    const [videoFiles, setVideoFiles] = useState<File[]>([]);
    const [videoJsOptions, setVideoJsOptions] = useState({
        autoplay: "play",
        controls: true,
        responsive: true,
        fluid: true,
        experimentalSvgIcons: true,
        bigPlayButton: false,
        sources: [
            {
                src: "",
                type: "video/mp4",
            },
        ],
    });

    useEffect(() => {
        if (!props.download) {
            setVideoFiles([]);
            return;
        }

        if (prevDownload?.infohash !== props.download?.infohash) {
            triblerService.getDownloadFiles(props.download.infohash).then((response) => {
                if (response !== undefined && !isErrorDict(response)) {
                    setVideoFiles(getStreamableFiles(response).sort((a, b) => (a.name > b.name ? 1 : -1)));
                } else {
                    setVideoFiles([]);
                }
            });
        }
    }, [props.download]);

    useEffect(() => {
        // By default we select the first streamable file in the download.
        setSelectedFile(videoFiles[0]);
    }, [videoFiles]);

    useEffect(() => {
        setVideoJsOptions((prevOptions) => ({
            ...prevOptions,
            sources: [
                {
                    src: "/api/downloads/" + props.download?.infohash + "/stream/" + selectedFile?.index,
                    type: "video/mp4",
                },
            ],
        }));
    }, [selectedFile]);

    return (
        <Dialog {...props}>
            <DialogContent className="sm:max-w-6xl">
                <DialogHeader>
                    <DialogTitle className="sr-only">{t("VideoPlayer")}</DialogTitle>
                </DialogHeader>
                <div>
                    <Popover open={open} onOpenChange={setOpen}>
                        <PopoverTrigger asChild>
                            <Button variant="outline" role="combobox" aria-expanded={open} className="justify-between">
                                {selectedFile
                                    ? videoFiles.find((videoFile) => videoFile.index === selectedFile.index)?.name
                                    : t("SelectVideoFile")}
                                <ChevronsUpDown className="ml-2 h-4 w-4 shrink-0 opacity-50" />
                            </Button>
                        </PopoverTrigger>
                        <PopoverContent className="w-[--radix-popover-trigger-width] p-0">
                            <Command>
                                <CommandInput placeholder={t("SearchVideoFile")} />
                                <CommandList>
                                    <CommandEmpty>{t("NoVideoFilesFound")}</CommandEmpty>
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
                                                    setSelectedFile(file);
                                                    setOpen(false);
                                                }}>
                                                <Check
                                                    className={cn(
                                                        "mr-2 h-4 w-4",
                                                        selectedFile?.index === videoFile.index
                                                            ? "opacity-100"
                                                            : "opacity-0"
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
                    <div className="h-3"></div>
                    <VideoJS options={videoJsOptions} open={props.open} />
                </div>
            </DialogContent>
        </Dialog>
    );
}

export const VideoJS = (props: {options: any; onReady?: any; open?: boolean}) => {
    const {i18n} = useTranslation();
    const language = i18n.language.replace("_", "-");
    const videoRef = React.useRef<HTMLDivElement>(null);
    const playerRef = React.useRef<ReturnType<typeof videojs> | null>(null);
    const {options, onReady} = props;
    const prevOpen = usePrevious(props.open);

    React.useEffect(() => {
        // Make sure Video.js player is only initialized once
        if (!playerRef.current) {
            // The Video.js player needs to be _inside_ the component el for React 18 Strict Mode.
            const videoElement = document.createElement("video-js");

            videoElement.classList.add("vjs-big-play-centered");
            if (!videoRef.current) return;
            videoRef.current.appendChild(videoElement);
            const player = (playerRef.current = videojs(
                videoElement,
                {...options, language, languages: playerLanguages},
                () => onReady && onReady(player)
            ));
        } else {
            const player = playerRef.current;
            player.language(language);
            const src_curr = player.currentSrc();
            const src_next = options.sources[0].src;

            if ((src_curr !== src_next && props.open) || (props.open && !prevOpen)) {
                console.log("Setting player source:" + src_next);
                player.autoplay(options.autoplay);
                player.src(options.sources);
            }
        }
    }, [options, videoRef, props.open, language]);

    // Destroy the player when the dialog closes, or HTTP connections will remain open.
    // This prevents videofiles from being locked.
    useEffect(() => {
        if (!props.open) {
            const player = playerRef.current;
            if (player && !player.isDisposed()) {
                player.dispose();
                playerRef.current = null;
            }
        }
    }, [props.open]);

    return (
        <div data-vjs-player>
            <div ref={videoRef} />
        </div>
    );
};

export default VideoJS;
