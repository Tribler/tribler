import { Download } from "@/models/download.model";
import { triblerService } from "@/services/tribler.service";
import { isErrorDict } from "@/services/reporting";
import toast from 'react-hot-toast';
import { Button } from "@/components/ui/button";
import {
    DropdownMenu,
    DropdownMenuContent,
    DropdownMenuItem,
    DropdownMenuLabel,
    DropdownMenuPortal,
    DropdownMenuSeparator,
    DropdownMenuSub,
    DropdownMenuSubContent,
    DropdownMenuSubTrigger,
    DropdownMenuTrigger
} from "@/components/ui/dropdown-menu";
import { CheckCheckIcon, ExternalLinkIcon, MoreHorizontal, Pause, Play, Trash, VenetianMaskIcon } from "lucide-react";
import { MoveIcon } from "@radix-ui/react-icons";
import { Dialog, DialogClose, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { useState } from "react";
import { Label } from "@/components/ui/label";
import { useTranslation } from "react-i18next";
import { PathInput } from "@/components/path-input";
import { downloadFile, downloadFilesAsZip } from "@/lib/utils";


export default function Actions({ selectedDownloads }: { selectedDownloads: Download[] }) {
    const { t } = useTranslation();
    const [removeDialogOpen, setRemoveDialogOpen] = useState(false);
    const [storageDialogOpen, setStorageDialogOpen] = useState(false);
    const [storageLocation, setStorageLocation] = useState('');

    const onPlay = () => {
        selectedDownloads.forEach((download) => {
            (async () => {
                const response = await triblerService.resumeDownload(download.infohash);
                if (response === undefined) {
                    toast.error(`${t("ToastErrorDownloadPlay")} ${t("ToastErrorGenNetworkErr")}`);
                } else if (isErrorDict(response)) {
                    toast.error(`${t("ToastErrorDownloadPlay")} ${response.error.message}`);
                }
            })();
        });
    }
    const onPause = () => {
        selectedDownloads.forEach((download) => {
            (async () => {
                const response = await triblerService.stopDownload(download.infohash);
                if (response === undefined) {
                    toast.error(`${t("ToastErrorDownloadStop")} ${t("ToastErrorGenNetworkErr")}`);
                } else if (isErrorDict(response)) {
                    toast.error(`${t("ToastErrorDownloadStop")} ${response.error.message}`);
                }
            })();
        });
    }
    const onRemove = (removeData: boolean) => {
        selectedDownloads.forEach((download) => {
            (async () => {
                const response = await triblerService.removeDownload(download.infohash, removeData);
                if (response === undefined) {
                    toast.error(`${t("ToastErrorDownloadRemove")} ${t("ToastErrorGenNetworkErr")}`);
                } else if (isErrorDict(response)) {
                    toast.error(`${t("ToastErrorDownloadRemove")} ${response.error.message}`);
                }
            })();
        });
        setRemoveDialogOpen(false);
    }
    const onRecheck = () => {
        selectedDownloads.forEach((download) => {
            (async () => {
                const response = await triblerService.recheckDownload(download.infohash);
                if (response === undefined) {
                    toast.error(`${t("ToastErrorDownloadCheck")} ${t("ToastErrorGenNetworkErr")}`);
                } else if (isErrorDict(response)) {
                    toast.error(`${t("ToastErrorDownloadCheck")} ${response.error.message}`);
                }
            })();
        });
    }
    const onExportTorrent = () => {
        const files = selectedDownloads.map((download) => ({
            uri: `/api/downloads/${download.infohash}/torrent`,
            name: `${download.infohash}.torrent`
        }));

        if (files.length == 1) downloadFile(files[0]);
        else if (files.length > 1) downloadFilesAsZip(files, 'torrents.zip');
    }
    const onMoveDownload = () => {
        if (selectedDownloads.length > 0) {
            setStorageLocation(selectedDownloads[0].destination);
            setStorageDialogOpen(true);
        }
    }
    const onMoveDownloadConfirmed = () => {
        selectedDownloads.forEach((download) => {
            triblerService.moveDownload(download.infohash, storageLocation).then(async (response) => {
                if (response === undefined) {
                    toast.error(`${t("ToastErrorDownloadMove")} ${t("ToastErrorGenNetworkErr")}`);
                } else if (isErrorDict(response)) {
                    toast.error(`${t("ToastErrorDownloadMove")} ${response.error.message}`);
                }
            });
        });
        setStorageDialogOpen(false);
    }
    const onSetHops = (hops: number) => {
        selectedDownloads.forEach((download) => {
            (async () => {
                const response = await triblerService.setDownloadHops(download.infohash, hops);
                if (response === undefined) {
                    toast.error(`${t("ToastErrorDownloadSetHops")} ${t("ToastErrorGenNetworkErr")}`);
                } else if (isErrorDict(response)) {
                    toast.error(`${t("ToastErrorDownloadSetHops")} ${response.error.message}`);
                }
            })();
        });
    }

    return (
        <>
            <p className="text-sm whitespace-nowrap pr-3">{t('WithSelected')}</p>
            <Button
                variant="outline"
                className="h-8 w-8 p-0"
                onClick={onPlay} disabled={selectedDownloads.length < 1}
            >
                <Play className="h-4 w-4" />
            </Button>
            <Button
                variant="outline"
                className="h-8 w-8 p-0"
                onClick={onPause}
                disabled={selectedDownloads.length < 1}
            >
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

            <Dialog open={removeDialogOpen} onOpenChange={setRemoveDialogOpen}>
                <DialogContent>
                    <DialogHeader>
                        <DialogTitle>{t('RemoveDownload')}</DialogTitle>
                        <DialogDescription>
                            {t('RemoveDownloadConfirm', { downloads: selectedDownloads.length })}
                        </DialogDescription>
                    </DialogHeader>
                    <DialogFooter>
                        <Button variant="outline" type="submit" onClick={() => { onRemove(false) }}>{t('RemoveDownload')}</Button>
                        <Button variant="outline" type="submit" onClick={() => { onRemove(true) }}>{t('RemoveDownloadData')}</Button>
                        <DialogClose asChild>
                            <Button variant="outline" type="button">
                                {t('Cancel')}
                            </Button>
                        </DialogClose>
                    </DialogFooter>
                </DialogContent>
            </Dialog>

            <Dialog open={storageDialogOpen} onOpenChange={setStorageDialogOpen}>
                <DialogContent>
                    <DialogHeader>
                        <DialogTitle>{t('ChangeStorage')}</DialogTitle>
                        <DialogDescription>
                            {t('ChangeStorageDescription')}
                        </DialogDescription>
                    </DialogHeader>
                    <div className="grid gap-6 py-4">
                        <div className="grid grid-cols-6 items-center gap-4">
                            <Label htmlFor="dest_dir" className="text-right">
                                {t('ChangeStorageLocation')}
                            </Label>
                            <PathInput
                                className="col-span-5"
                                path={storageLocation}
                                onPathChange={(path) => setStorageLocation(path)}
                            />
                        </div>
                    </div>
                    <DialogFooter>
                        <Button
                            variant="outline"
                            type="submit"
                            disabled={selectedDownloads.every((d) => d.destination === storageLocation)}
                            onClick={() => { onMoveDownloadConfirmed() }}>
                            {t('ChangeStorageButton')}
                        </Button>
                        <DialogClose asChild>
                            <Button variant="outline" type="button">
                                {t('Cancel')}
                            </Button>
                        </DialogClose>
                    </DialogFooter>
                </DialogContent>
            </Dialog>

            <DropdownMenu>
                <DropdownMenuTrigger asChild>
                    <Button variant="outline" className="h-8 w-8 p-0">
                        <MoreHorizontal className="h-4 w-4" />
                    </Button>
                </DropdownMenuTrigger>
                <DropdownMenuContent align="end">
                    <DropdownMenuLabel>{t('Actions')}</DropdownMenuLabel>
                    <DropdownMenuSeparator />
                    <DropdownMenuItem onClick={onRecheck} disabled={selectedDownloads.length < 1}>
                        <CheckCheckIcon className="mr-2 h-4 w-4" />
                        {t('ForceRecheck')}
                    </DropdownMenuItem>
                    <DropdownMenuItem onClick={() => onExportTorrent()} disabled={selectedDownloads.length < 1}>
                        <ExternalLinkIcon className="mr-2 h-4 w-4" />
                        {t('ExportTorrent')}
                    </DropdownMenuItem>
                    <DropdownMenuItem onClick={() => { onMoveDownload() }} disabled={selectedDownloads.length < 1}>
                        <MoveIcon className="mr-2 h-4 w-4" />
                        {t('MoveStorage')}
                    </DropdownMenuItem>
                    <DropdownMenuSub>
                        <DropdownMenuSubTrigger disabled={selectedDownloads.length < 1} className={`${selectedDownloads.length < 1 ? "opacity-50" : ""}`}>
                            <VenetianMaskIcon className="mr-2 h-4 w-4" />
                            <span>{t('ChangeAnonymity')}</span>
                        </DropdownMenuSubTrigger>
                        <DropdownMenuPortal>
                            <DropdownMenuSubContent>
                                <DropdownMenuItem onClick={() => { onSetHops(0) }}>
                                    <span>{t('ZeroHops')}</span>
                                </DropdownMenuItem>
                                <DropdownMenuSeparator />
                                <DropdownMenuItem onClick={() => { onSetHops(1) }}>
                                    <span>{t('OneHop')}</span>
                                </DropdownMenuItem>
                                <DropdownMenuItem onClick={() => { onSetHops(2) }}>
                                    <span>{t('TwoHops')}</span>
                                </DropdownMenuItem>
                                <DropdownMenuItem onClick={() => { onSetHops(3) }}>
                                    <span>{t('ThreeHops')}</span>
                                </DropdownMenuItem>
                            </DropdownMenuSubContent>
                        </DropdownMenuPortal>
                    </DropdownMenuSub>
                </DropdownMenuContent>
            </DropdownMenu>
        </>
    )
}
