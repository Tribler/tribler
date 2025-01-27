import { useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import toast from 'react-hot-toast';
import { Button } from "./ui/button";
import { PlusIcon, Cloud, File as FileIcon } from "lucide-react";
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuSeparator, DropdownMenuTrigger } from "./ui/dropdown-menu";
import { Dialog, DialogClose, DialogContent, DialogFooter, DialogHeader, DialogTitle } from "./ui/dialog";
import { triblerService } from "@/services/tribler.service";
import { isErrorDict } from "@/services/reporting";
import { Input } from "./ui/input";
import SaveAs from "@/dialogs/SaveAs";
import CreateTorrent from "@/dialogs/CreateTorrent";
import { useTranslation } from "react-i18next";


export function AddTorrent() {
    const { t } = useTranslation();
    const navigate = useNavigate();
    const fileInputRef = useRef<HTMLInputElement | null>(null);
    const uriInputRef = useRef<HTMLInputElement | null>(null);

    const [urlDialogOpen, setUrlDialogOpen] = useState<boolean>(false);
    const [uriInput, setUriInput] = useState('');

    const [saveAsDialogOpen, setSaveAsDialogOpen] = useState<boolean>(false);

    const [createDialogOpen, setCreateDialogOpen] = useState<boolean>(false);

    const [torrent, setTorrent] = useState<File | undefined>();

    return (
        <>
            <DropdownMenu>
                <DropdownMenuTrigger asChild>
                    <Button className="h-10 pl-2 mb-2 w-full justify-start rounded-none">
                        <PlusIcon className="mr-2" />
                        {t('AddTorrent')}
                    </Button>
                </DropdownMenuTrigger>
                <DropdownMenuContent align="end">
                    <DropdownMenuItem
                        onClick={() => {
                            setUriInput('');
                            setUrlDialogOpen(true);
                        }}>
                        <Cloud className="mr-2 h-4 w-4" />
                        {t('ImportTorrentURL')}
                    </DropdownMenuItem>
                    <DropdownMenuItem
                        onClick={() => {
                            if (fileInputRef && fileInputRef.current) {
                                fileInputRef.current.click();
                            }
                        }}>
                        <FileIcon className="mr-2 h-4 w-4" />
                        {t('ImportTorrentFile')}
                    </DropdownMenuItem>
                    <DropdownMenuSeparator />
                    <DropdownMenuItem
                        onClick={() => {
                            setCreateDialogOpen(true);
                        }}>
                        <PlusIcon className="mr-2 h-4 w-4" />
                        {t('CreateTorrent')}
                    </DropdownMenuItem>
                </DropdownMenuContent>
            </DropdownMenu>

            <Dialog open={urlDialogOpen} onOpenChange={setUrlDialogOpen}>
                <DialogContent>
                    <DialogHeader>
                        <DialogTitle>{t('MagnetDialogHeader')}</DialogTitle>
                    </DialogHeader>
                    <div className="grid gap-1 py-4 text-sm">
                        {t('MagnetDialogInputLabel')}
                        <div className="grid grid-cols-6 items-center gap-4">
                            <Input
                                ref={uriInputRef}
                                id="uri"
                                className="col-span-5 pt-0"
                            />
                        </div>
                    </div>
                    <DialogFooter>
                        <Button
                            variant="outline"
                            type="submit"
                            onClick={() => {
                                if (uriInputRef.current?.value) {
                                    setUriInput(uriInputRef.current.value);
                                    setTorrent(undefined);
                                    setUrlDialogOpen(false);
                                    (async () => {
                                        if (uriInputRef.current !== null) {
                                            const response = await triblerService.getMetainfo(uriInputRef.current.value, true);
                                            if (response === undefined) {
                                                toast.error(`${t("ToastErrorDownloadStart")} ${t("ToastErrorGenNetworkErr")}`);
                                            } else if (isErrorDict(response)){
                                                toast.error(`${t("ToastErrorDownloadStart")} ${response.error.message}`);
                                            } else {
                                                setSaveAsDialogOpen(true);
                                            }
                                        }
                                    })();
                                }
                            }}>
                            {t('Add')}
                        </Button>
                        <DialogClose asChild>
                            <Button variant="outline" type="button">
                                {t('Cancel')}
                            </Button>
                        </DialogClose>
                    </DialogFooter>
                </DialogContent>
            </Dialog>

            <SaveAs
                open={saveAsDialogOpen}
                onOpenChange={setSaveAsDialogOpen}
                torrent={torrent}
                uri={uriInput}
            />

            <CreateTorrent
                open={createDialogOpen}
                onOpenChange={setCreateDialogOpen}
            />

            <input
                style={{ display: 'none' }}
                ref={fileInputRef}
                type="file"
                accept=".torrent"
                onChange={(event) => {
                    if (!event.target.files || event.target.files.length === 0) {
                        return;
                    }
                    const files = Array.from(event.target.files as ArrayLike<File>);
                    event.target.value = '';

                    if (files.length === 1 && triblerService.guiSettings.ask_download_settings !== false) {
                        setSaveAsDialogOpen(true);
                        setTorrent(files[0]);
                    }
                    else {
                        for (let file of files) {
                            (async () => {
                                const response = await triblerService.startDownloadFromFile(file);
                                if (response === undefined) {
                                    toast.error(`${t("ToastErrorDownloadStart")} ${t("ToastErrorGenNetworkErr")}`);
                                } else if (isErrorDict(response)){
                                    toast.error(`${t("ToastErrorDownloadStart")} ${response.error.message}`);
                                }
                             })();
                        }
                    }
                    navigate("/downloads/all");
                }}
                multiple
            />
        </>
    )
}
