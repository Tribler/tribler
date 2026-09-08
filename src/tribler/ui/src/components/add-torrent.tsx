import {useEffect, useRef, useState} from "react";
import {useNavigate} from "react-router-dom";
import toast from "react-hot-toast";
import {Button} from "./ui/button";
import {PlusIcon, Cloud, File as FileIcon, Server} from "lucide-react";
import {
    DropdownMenu,
    DropdownMenuContent,
    DropdownMenuItem,
    DropdownMenuSeparator,
    DropdownMenuTrigger,
} from "./ui/dropdown-menu";
import {
    Dialog,
    DialogClose,
    DialogContent,
    DialogDescription,
    DialogFooter,
    DialogHeader,
    DialogTitle,
} from "./ui/dialog";
import {triblerService} from "@/services/tribler.service";
import {isErrorDict} from "@/services/reporting";
import {Input} from "./ui/input";
import SaveAs from "@/dialogs/SaveAs";
import CreateTorrent from "@/dialogs/CreateTorrent";
import {useTranslation} from "react-i18next";
import SelectRemotePath from "@/dialogs/SelectRemotePath";

/**
 * This Promise throttles the number of SaveAs dialogs [Warning: this is where it gets weird.]
 * React state changes cause component re-renders. If we were to store this in the AddTorrent component, updating the
 * promise with the new entry in the callback chain would re-render the component. This does work within a callback
 * chain that is managed within the component itself. However, when mixing with an event (OnCoreAskDownload), this would
 * cause a re-render that voids the previous state (deleting the previous queue of SaveAs dialogs). That's not what
 * we want.
 * So, we have to store saveAsOpenQueue outside of AddTorrent. This causes its own set of weird stuff, as you will now
 * be stuck with "old" Promises that have to complete their unrendered setters. Thankfully, React cleans this up through
 * its own internal black magic.
 */
let saveAsOpenQueue = new Promise<void>((resolve, reject) => resolve());

export function AddTorrent() {
    const {t} = useTranslation();
    const navigate = useNavigate();
    const fileInputRef = useRef<HTMLInputElement | null>(null);
    const uriInputRef = useRef<HTMLInputElement | null>(null);

    const [urlDialogOpen, setUrlDialogOpen] = useState<boolean>(false);
    const [uriInput, setUriInput] = useState("");

    const [remoteTorrentDialogOpen, setRemoteTorrentDialogOpen] = useState<boolean>(false);

    const [saveAsDialogOpen, setSaveAsDialogOpen] = useState<boolean>(false);
    const [saveAsClosed, setSaveAsClosed] = useState<{callback: ((value: void | PromiseLike<void>) => void) | null}>({
        callback: null,
    });

    const [createDialogOpen, setCreateDialogOpen] = useState<boolean>(false);

    const [torrent, setTorrent] = useState<File | undefined>();

    async function addSaveAsQueue(uri: string, file: File | undefined) {
        saveAsOpenQueue = saveAsOpenQueue.then(async () => new Promise((resolve, reject) => {
            setUriInput(uri);
            setTorrent(file);
            setSaveAsClosed({callback: resolve});
            setSaveAsDialogOpen(true);
        }));
    }

    useEffect(() => {
        (async () => {
            triblerService.addEventListener("ask_add_download", OnCoreAskDownload);
        })();
        return () => {
            (async () => {
                triblerService.removeEventListener("ask_add_download", OnCoreAskDownload);
            })();
        };
    }, []);

    const OnCoreAskDownload = async (event: MessageEvent) => {
        const message = JSON.parse(event.data);
        if (message.uri) {
            await addSaveAsQueue(message.uri, undefined);
        }
    };

    return (
        <>
            <DropdownMenu>
                <DropdownMenuTrigger asChild>
                    <Button className="h-10 pl-2 mb-2 w-full justify-start rounded-none">
                        <PlusIcon className="mr-2" />
                        {t("AddTorrent")}
                    </Button>
                </DropdownMenuTrigger>
                <DropdownMenuContent align="end">
                    <DropdownMenuItem
                        onClick={() => {
                            setUriInput("");
                            setUrlDialogOpen(true);
                        }}>
                        <Cloud className="mr-2 h-4 w-4" />
                        {t("ImportTorrentURL")}
                    </DropdownMenuItem>
                    <DropdownMenuItem
                        onClick={() => {
                            if (fileInputRef && fileInputRef.current) {
                                fileInputRef.current.click();
                            }
                        }}>
                        <FileIcon className="mr-2 h-4 w-4" />
                        {t("ImportTorrentFile")}
                    </DropdownMenuItem>
                    {location.hostname !== "localhost" && location.hostname !== "127.0.0.1" && (
                        <DropdownMenuItem
                            onClick={() => {
                                setRemoteTorrentDialogOpen(true);
                            }}>
                            <Server className="mr-2 h-4 w-4" />
                            {t("ImportRemoteTorrentFile")}
                        </DropdownMenuItem>
                    )}
                    <DropdownMenuSeparator />
                    <DropdownMenuItem
                        onClick={() => {
                            setCreateDialogOpen(true);
                        }}>
                        <PlusIcon className="mr-2 h-4 w-4" />
                        {t("CreateTorrent")}
                    </DropdownMenuItem>
                </DropdownMenuContent>
            </DropdownMenu>

            <Dialog open={urlDialogOpen} onOpenChange={setUrlDialogOpen}>
                <DialogContent>
                    <DialogHeader>
                        <DialogTitle>{t("MagnetDialogHeader")}</DialogTitle>
                        <DialogDescription></DialogDescription>
                    </DialogHeader>
                    <div className="grid gap-1 py-4 text-sm">
                        {t("MagnetDialogInputLabel")}
                        <div className="grid grid-cols-6 items-center gap-4">
                            <Input ref={uriInputRef} id="uri" className="col-span-5 pt-0" />
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
                                            const response = await triblerService.getMetainfo(
                                                uriInputRef.current.value,
                                                true
                                            );
                                            if (response === undefined) {
                                                toast.error(
                                                    `${t("ToastErrorDownloadStart")} ${t("ToastErrorGenNetworkErr")}`
                                                );
                                            } else if (isErrorDict(response)) {
                                                toast.error(
                                                    `${t("ToastErrorDownloadStart")} ${response.error.message}`
                                                );
                                            } else {
                                                setSaveAsDialogOpen(true);
                                            }
                                        }
                                    })();
                                }
                            }}>
                            {t("Add")}
                        </Button>
                        <DialogClose asChild>
                            <Button variant="outline" type="button">
                                {t("Cancel")}
                            </Button>
                        </DialogClose>
                    </DialogFooter>
                </DialogContent>
            </Dialog>

            <SelectRemotePath
                initialPath={""}
                selectDir={false}
                open={remoteTorrentDialogOpen}
                onOpenChange={setRemoteTorrentDialogOpen}
                onSelect={(path) => {
                    setUriInput(`file:///${path.replace(/\\/g, "/")}`);
                    setTorrent(undefined);
                    setSaveAsDialogOpen(true);
                }}
                filterFn={(path) => path.dir || path.name.endsWith(".torrent")}
            />

            <SaveAs
                open={saveAsDialogOpen}
                onOpenChange={(value) => {
                    setSaveAsDialogOpen(value);
                    if (!value && saveAsClosed.callback) {
                        saveAsClosed.callback(undefined);
                    }
                }}
                torrent={torrent}
                uri={uriInput}
            />

            <CreateTorrent open={createDialogOpen} onOpenChange={setCreateDialogOpen} />

            <input
                style={{display: "none"}}
                ref={fileInputRef}
                type="file"
                accept=".torrent"
                onChange={async (event) => {
                    if (!event.target.files || event.target.files.length === 0) {
                        return;
                    }
                    const files = Array.from(event.target.files as ArrayLike<File>);
                    event.target.value = "";
                    const settings = await triblerService.getSettings();

                    if (settings === undefined) {
                        toast.error(`${t("ToastErrorDownloadStart")} ${t("ToastErrorGenNetworkErr")}`);
                        return;
                    } else if (isErrorDict(settings)) {
                        toast.error(`${t("ToastErrorDownloadStart")} ${settings.error.message}`);
                        return;
                    }

                    if (settings?.libtorrent?.ask_download_settings === true) {
                        (async () => {
                            for (let file of files) {
                                await addSaveAsQueue("", file);
                            }
                        })();
                    } else {
                        for (let file of files) {
                            (async () => {
                                const response = await triblerService.startDownloadFromFile(file);
                                if (response === undefined) {
                                    toast.error(`${t("ToastErrorDownloadStart")} ${t("ToastErrorGenNetworkErr")}`);
                                } else if (isErrorDict(response)) {
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
    );
}
