import { Download } from "@/models/download.model";
import { triblerService } from "@/services/tribler.service";
import { ErrorDict, isErrorDict } from "@/services/reporting";
import toast from 'react-hot-toast';
import { Button } from "@/components/ui/button";
import { CheckCheckIcon, Clapperboard, ExternalLinkIcon, Pause, Play, Trash, VenetianMaskIcon } from "lucide-react";
import { MoveIcon } from "@radix-ui/react-icons";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { downloadFile, downloadFilesAsZip } from "@/lib/utils";
import { TFunction } from "i18next";
import { ContextMenuContent, ContextMenuItem, ContextMenuSeparator, ContextMenuSub, ContextMenuSubContent, ContextMenuSubTrigger } from "@/components/ui/context-menu";
import MoveStorage from "@/dialogs/MoveStorage";
import ConfirmRemove from "@/dialogs/ConfirmRemove";
import { VideoDialog } from "@/dialogs/Videoplayer";
import { filterActive, filterInactive } from ".";


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
            handleError(response, t("ToastErrorDownloadPlay"), t("ToastErrorGenNetworkErr")))
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

function moveDownloads(selectedDownloads: Download[], storageLocation: string, t: TFunction) {
    selectedDownloads.forEach((download) => {
        triblerService.moveDownload(download.infohash, storageLocation).then((response) =>
            handleError(response, t("ToastErrorDownloadMove"), t("ToastErrorGenNetworkErr")))
    });
}

function setHops(selectedDownloads: Download[], hops: number, t: TFunction) {
    selectedDownloads.forEach((download) => {
        triblerService.setDownloadHops(download.infohash, hops).then((response) =>
            handleError(response, t("ToastErrorDownloadSetHops"), t("ToastErrorGenNetworkErr")))
    });
}

export function ActionButtons({ selectedDownloads }: { selectedDownloads: Download[] }) {
    const { t } = useTranslation();

    const [removeDialogOpen, setRemoveDialogOpen] = useState(false);

    return (
        <>
            <p className="text-sm whitespace-nowrap pr-3">{t('WithSelected')}</p>
            <Button
                variant="outline"
                className="h-8 w-8 p-0"
                onClick={() => resumeDownloads(selectedDownloads, t)}
                disabled={selectedDownloads.length < 1
                    || selectedDownloads.every((d) => filterActive.includes(d.status_code))}>
                <Play className="h-4 w-4" />
            </Button>
            <Button
                variant="outline"
                className="h-8 w-8 p-0"
                onClick={() => stopDownloads(selectedDownloads, t)}
                disabled={selectedDownloads.length < 1
                    || selectedDownloads.every((d) => filterInactive.includes(d.status_code))}>
                <Pause className="h-4 w-4" />
            </Button>
            <Button
                variant="outline"
                className="h-8 w-8 p-0"
                onClick={() => setRemoveDialogOpen(true)}
                disabled={selectedDownloads.length < 1}
            >
                <Trash className="h-4 w-4" />
            </Button>

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
                        {"Stream"}
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
                <ContextMenuItem
                    className="hover:bg-neutral-200 dark:hover:bg-neutral-800"
                    onClick={() => (selectedDownloads.length > 0) && setStorageDialogOpen(true)}
                    disabled={selectedDownloads.length < 1}>
                    <MoveIcon className="w-4 ml-2 mr-3" />
                    {t('MoveStorage')}
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
