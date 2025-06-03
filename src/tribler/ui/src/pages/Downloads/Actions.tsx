import { Download } from "@/models/download.model";
import { triblerService } from "@/services/tribler.service";
import { ErrorDict, isErrorDict } from "@/services/reporting";
import toast from 'react-hot-toast';
import { Button } from "@/components/ui/button";
import { ArrowDown, ArrowUp, CheckCheckIcon, Clapperboard, ExternalLinkIcon, Pause, Play, Trash, VenetianMaskIcon } from "lucide-react";
import { MoveIcon } from "@radix-ui/react-icons";
import { useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { downloadFile, downloadFilesAsZip, formatBytes } from "@/lib/utils";
import { TFunction } from "i18next";
import { ContextMenuContent, ContextMenuItem, ContextMenuRadioGroup, ContextMenuRadioItem, ContextMenuSeparator, ContextMenuSub, ContextMenuSubContent, ContextMenuSubTrigger } from "@/components/ui/context-menu";
import MoveStorage from "@/dialogs/MoveStorage";
import ConfirmRemove from "@/dialogs/ConfirmRemove";
import { VideoDialog } from "@/dialogs/Videoplayer";
import { filterActive, filterInactive } from ".";
import { EasyTooltip } from "@/components/ui/tooltip";

const defaultLimits = [5 * 1024, 15 * 1024, 50 * 1024, 100 * 1024, 150 * 1024, -1];

function handleError(response: undefined | ErrorDict | boolean, errorMsg: string, undefinedMsg: string) {
    if (response === undefined) {
        toast.error(`${errorMsg} ${undefinedMsg}`);
    } else if (isErrorDict(response)) {
        toast.error(`${errorMsg} ${response.error.message}`);
    }
}

function resumeDownloads(selectedDownloads: Download[], t: TFunction) {
    selectedDownloads.forEach((download) => {
        triblerService.resumeDownload(download.infohash).then((response) =>
            handleError(response, t("ToastErrorDownloadStart"), t("ToastErrorGenNetworkErr")))
    });
}

function stopDownloads(selectedDownloads: Download[], t: TFunction) {
    selectedDownloads.forEach((download) => {
        triblerService.stopDownload(download.infohash).then((response) =>
            handleError(response, t("ToastErrorDownloadStop"), t("ToastErrorGenNetworkErr")))
    });
}

function removeDownloads(selectedDownloads: Download[], removeData: boolean, t: TFunction) {
    selectedDownloads.forEach((download) => {
        triblerService.removeDownload(download.infohash, removeData).then((response) =>
            handleError(response, t("ToastErrorDownloadRemove"), t("ToastErrorGenNetworkErr")))
    });
}

function recheckDownloads(selectedDownloads: Download[], t: TFunction) {
    selectedDownloads.forEach((download) => {
        triblerService.recheckDownload(download.infohash).then((response) =>
            handleError(response, t("ToastErrorDownloadCheck"), t("ToastErrorGenNetworkErr")))
    });
}

function exportTorrents(selectedDownloads: Download[]) {
    const files = selectedDownloads.map((download) => ({
        uri: `/api/downloads/${download.infohash}/torrent`,
        name: `${download.infohash}.torrent`
    }));

    if (files.length == 1) downloadFile(files[0]);
    else if (files.length > 1) downloadFilesAsZip(files, 'torrents.zip');
}

function moveDownloads(selectedDownloads: Download[], storageLocation: string, completedLocation: string, t: TFunction) {
    selectedDownloads.forEach((download) => {
        triblerService.moveDownload(download.infohash, storageLocation, completedLocation).then((response) =>
            handleError(response, t("ToastErrorDownloadMove"), t("ToastErrorGenNetworkErr")))
    });
}

function setHops(selectedDownloads: Download[], hops: number, t: TFunction) {
    selectedDownloads.forEach((download) => {
        triblerService.setDownloadHops(download.infohash, hops).then((response) =>
            handleError(response, t("ToastErrorDownloadSetHops"), t("ToastErrorGenNetworkErr")))
    });
}

function setBandwidthLimit(selectedDownloads: Download[], value: number | undefined, direction: "up" | "down", t: TFunction) {
    if (value === undefined) return
    selectedDownloads.forEach((download) => {
        let result;
        if (direction === "up") {
            download.upload_limit = value;
            result = triblerService.setUploadLimit(download.infohash, value);
        }
        else {
            download.download_limit = value;
            result = triblerService.setDownloadLimit(download.infohash, value);
        }
        result.then((response) => handleError(response, t("ToastErrorSetBandwidthLimit"), t("ToastErrorGenNetworkErr")));
    });
}

function getBandwidthLimit(selectedDownloads: Download[], direction: "up" | "down", noDefaults: boolean = false): number | undefined {
    const limits = selectedDownloads.map((download) => direction === "up" ? download.upload_limit : download.download_limit);
    const allEqual = limits.every((val, i, arr) => val === arr[0]);
    if (noDefaults) return allEqual && !defaultLimits.includes(limits[0]) ? limits[0] : undefined;
    return allEqual ? limits[0] : undefined;
}

export function ActionButtons({ selectedDownloads }: { selectedDownloads: Download[] }) {
    const { t } = useTranslation();

    const [removeDialogOpen, setRemoveDialogOpen] = useState(false);

    return (
        <>
            <p className="text-sm whitespace-nowrap pr-3">{t('WithSelected')}</p>

            <EasyTooltip content={t('Start')}>
                <Button
                    variant="outline"
                    className="h-8 w-8 p-0"
                    onClick={() => resumeDownloads(selectedDownloads, t)}
                    disabled={selectedDownloads.length < 1
                        || selectedDownloads.every((d) => filterActive.includes(d.status_code))}>
                    <Play className="h-4 w-4" />
                </Button>
            </EasyTooltip>

            <EasyTooltip content={t('Stop')}>
                <Button
                    variant="outline"
                    className="h-8 w-8 p-0"
                    onClick={() => stopDownloads(selectedDownloads, t)}
                    disabled={selectedDownloads.length < 1
                        || selectedDownloads.every((d) => filterInactive.includes(d.status_code))}>
                    <Pause className="h-4 w-4" />
                </Button>
            </EasyTooltip>

            <EasyTooltip content={t('Remove')}>
                <Button
                    variant="outline"
                    className="h-8 w-8 p-0"
                    onClick={() => setRemoveDialogOpen(true)}
                    disabled={selectedDownloads.length < 1}
                >
                    <Trash className="h-4 w-4" />
                </Button>
            </EasyTooltip>

            <ConfirmRemove
                open={removeDialogOpen}
                onOpenChange={setRemoveDialogOpen}
                selectedDownloads={selectedDownloads}
                onRemove={removeDownloads} />
        </>
    )
}

export function ActionMenu({ selectedDownloads }: { selectedDownloads: Download[] }) {
    const { t } = useTranslation();

    const uploadLimitRef = useRef<HTMLInputElement | null>(null);
    const downloadLimitRef = useRef<HTMLInputElement | null>(null);

    const [removeDialogOpen, setRemoveDialogOpen] = useState(false);
    const [storageDialogOpen, setStorageDialogOpen] = useState(false);
    const [videoDialogOpen, setVideoDialogOpen] = useState<boolean>(false);
    const [videoDownload, setVideoDownload] = useState<Download | null>(null);

    return (
        <>
            <ContextMenuContent className="w-64 bg-neutral-50 dark:bg-neutral-950">
                <ContextMenuItem
                    className="hover:bg-neutral-200 dark:hover:bg-neutral-800"
                    onClick={() => resumeDownloads(selectedDownloads, t)}
                    disabled={selectedDownloads.length < 1
                        || selectedDownloads.every((d) => filterActive.includes(d.status_code))}>
                    <Play className="w-4 ml-2 mr-3" />
                    {t('Start')}
                </ContextMenuItem>
                <ContextMenuItem
                    className="hover:bg-neutral-200 dark:hover:bg-neutral-800"
                    onClick={() => stopDownloads(selectedDownloads, t)}
                    disabled={selectedDownloads.length < 1
                        || selectedDownloads.every((d) => filterInactive.includes(d.status_code))}>
                    <Pause className="w-4 ml-2 mr-3" />
                    {t('Stop')}
                </ContextMenuItem>
                {triblerService.guiSettings.dev_mode && navigator.userAgent.includes("Chrome") &&
                    <ContextMenuItem
                        className="hover:bg-neutral-200 dark:hover:bg-neutral-800"
                        onClick={() => {
                            console.log("Streaming...", selectedDownloads[0]);
                            if (selectedDownloads.length == 1) {
                                setVideoDialogOpen(true);
                                setVideoDownload(selectedDownloads[0]);
                            }
                        }}
                        disabled={selectedDownloads.length !== 1 || selectedDownloads[0].streamable !== true}>
                        <Clapperboard className="w-4 ml-2 mr-3" />
                        {t("Stream")}
                    </ContextMenuItem>
                }
                <ContextMenuSeparator />
                <ContextMenuItem
                    className="hover:bg-neutral-200 dark:hover:bg-neutral-800"
                    onClick={() => (selectedDownloads.length > 0) && setRemoveDialogOpen(true)}
                    disabled={selectedDownloads.length < 1}>
                    <Trash className="w-4 ml-2 mr-3" />
                    {t('Remove')}
                </ContextMenuItem>
                <ContextMenuSeparator />
                <ContextMenuSub>
                    <ContextMenuSubTrigger
                        disabled={selectedDownloads.length < 1}
                        className={`${selectedDownloads.length < 1 ? "opacity-50" : ""}`}>
                        <ArrowDown className="w-4 ml-2 mr-3" />
                        {t("DownloadLimit")}
                    </ContextMenuSubTrigger>
                    <ContextMenuSubContent className="w-48 bg-neutral-50 dark:bg-neutral-950">
                        <ContextMenuRadioGroup
                            value={String(getBandwidthLimit(selectedDownloads, "down"))}>
                            {defaultLimits.map((limit) => (
                                <ContextMenuRadioItem
                                    value={limit.toString()}
                                    onSelect={() => setBandwidthLimit(selectedDownloads, limit, "down", t)}>
                                    <span>{limit === -1 ? "unlimited" : formatBytes(limit, 0)}</span>
                                </ContextMenuRadioItem >
                            ))}
                            <ContextMenuRadioItem
                                className="space-x-2"
                                value={String(getBandwidthLimit(selectedDownloads, "down", true) || -2)}>
                                <input
                                    ref={downloadLimitRef}
                                    type="number"
                                    defaultValue={(getBandwidthLimit(selectedDownloads, "down", true) || 1024) / 1024}
                                    className="bg-white text-black w-[75px] mr-1"
                                    onClick={(e) => e.preventDefault()}
                                    min={1} max={1024 * 10}>
                                </input>
                                KiB/s
                                <Button
                                    className="outline px-1 py-1 h-6 ml-1"
                                    onClick={() => {
                                        if (downloadLimitRef.current?.value) {
                                            setBandwidthLimit(selectedDownloads, +downloadLimitRef.current?.value * 1024, "down", t)
                                        }
                                    }}>Set</Button>
                            </ContextMenuRadioItem>
                        </ContextMenuRadioGroup>
                    </ContextMenuSubContent>
                </ContextMenuSub>
                <ContextMenuSub>
                    <ContextMenuSubTrigger
                        disabled={selectedDownloads.length < 1}
                        className={`${selectedDownloads.length < 1 ? "opacity-50" : ""}`}>
                        <ArrowUp className="w-4 ml-2 mr-3" />
                        {t("UploadLimit")}
                    </ContextMenuSubTrigger>
                    <ContextMenuSubContent className="w-48 bg-neutral-50 dark:bg-neutral-950">
                        <ContextMenuRadioGroup
                            value={String(getBandwidthLimit(selectedDownloads, "up"))}>
                            {defaultLimits.map((limit) => (
                                <ContextMenuRadioItem
                                    value={limit.toString()}
                                    onSelect={() => setBandwidthLimit(selectedDownloads, limit, "up", t)}>
                                    <span>{limit === -1 ? "unlimited" : formatBytes(limit, 0)}</span>
                                </ContextMenuRadioItem >
                            ))}
                            <ContextMenuRadioItem
                                className="space-x-2"
                                value={String(getBandwidthLimit(selectedDownloads, "up", true) || -2)}>
                                <input
                                    ref={uploadLimitRef}
                                    type="number"
                                    defaultValue={(getBandwidthLimit(selectedDownloads, "up", true) || 1024) / 1024}
                                    className="bg-white text-black w-[75px] mr-1"
                                    onClick={(e) => e.preventDefault()}
                                    min={1} max={1024 * 10}>
                                </input>
                                KiB/s
                                <Button
                                    className="outline px-1 py-1 h-6 ml-1"
                                    onClick={() => {
                                        if (uploadLimitRef.current?.value) {
                                            setBandwidthLimit(selectedDownloads, +uploadLimitRef.current?.value * 1024, "up", t)
                                        }
                                    }}>Set</Button>
                            </ContextMenuRadioItem>
                        </ContextMenuRadioGroup>
                    </ContextMenuSubContent>
                </ContextMenuSub>
                <ContextMenuItem
                    className="hover:bg-neutral-200 dark:hover:bg-neutral-800"
                    onClick={() => (selectedDownloads.length > 0) && setStorageDialogOpen(true)}
                    disabled={selectedDownloads.length < 1}>
                    <MoveIcon className="w-4 ml-2 mr-3" />
                    {t('MoveStorage')}..
                </ContextMenuItem>
                <ContextMenuItem
                    className="hover:bg-neutral-200 dark:hover:bg-neutral-800"
                    onClick={() => recheckDownloads(selectedDownloads, t)}
                    disabled={selectedDownloads.length < 1}>
                    <CheckCheckIcon className="w-4 ml-2 mr-3" />
                    {t('ForceRecheck')}
                </ContextMenuItem>
                <ContextMenuItem
                    className="hover:bg-neutral-200 dark:hover:bg-neutral-800"
                    onClick={() => exportTorrents(selectedDownloads)}
                    disabled={selectedDownloads.length < 1}>
                    <ExternalLinkIcon className="w-4 ml-2 mr-3" />
                    {t('ExportTorrent')}
                </ContextMenuItem>
                <ContextMenuSub>
                    <ContextMenuSubTrigger
                        disabled={selectedDownloads.length < 1}
                        className={`${selectedDownloads.length < 1 ? "opacity-50" : ""}`}>
                        <VenetianMaskIcon className="w-4 ml-2 mr-3" />
                        {t('ChangeAnonymity')}
                    </ContextMenuSubTrigger>
                    <ContextMenuSubContent className="w-48 bg-neutral-50 dark:bg-neutral-950">
                        <ContextMenuItem onClick={() => { setHops(selectedDownloads, 0, t) }}>
                            <span>{t('ZeroHops')}</span>
                        </ContextMenuItem>
                        <ContextMenuItem onClick={() => { setHops(selectedDownloads, 1, t) }}>
                            <span>{t('OneHop')}</span>
                        </ContextMenuItem>
                        <ContextMenuItem onClick={() => { setHops(selectedDownloads, 2, t) }}>
                            <span>{t('TwoHops')}</span>
                        </ContextMenuItem>
                        <ContextMenuItem onClick={() => { setHops(selectedDownloads, 3, t) }}>
                            <span>{t('ThreeHops')}</span>
                        </ContextMenuItem>
                    </ContextMenuSubContent>
                </ContextMenuSub>
            </ContextMenuContent>

            <MoveStorage
                open={storageDialogOpen}
                onOpenChange={setStorageDialogOpen}
                selectedDownloads={selectedDownloads}
                onMove={moveDownloads} />
            <ConfirmRemove
                open={removeDialogOpen}
                onOpenChange={setRemoveDialogOpen}
                selectedDownloads={selectedDownloads}
                onRemove={removeDownloads} />
            <VideoDialog
                open={videoDialogOpen}
                onOpenChange={setVideoDialogOpen}
                download={videoDownload}
            />
        </>
    )
}
