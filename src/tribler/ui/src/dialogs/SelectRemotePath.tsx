import { useEffect, useState } from "react";
import toast from 'react-hot-toast';
import { triblerService } from "@/services/tribler.service";
import { isErrorDict } from "@/services/reporting";
import { Dialog, DialogClose, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { DialogProps } from "@radix-ui/react-dialog";
import { JSX } from "react/jsx-runtime";
import { useTranslation } from "react-i18next";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Folder, File as FileIcon, FolderPlus } from "lucide-react";
import { Path } from "@/models/path.model";
import { ContextMenu, ContextMenuContent, ContextMenuItem, ContextMenuTrigger } from "@/components/ui/context-menu";
import { Label } from "@/components/ui/label";
import { Input } from "@/components/ui/input";


interface SelectRemotePathProps {
    initialPath: string,
    selectDir: boolean,
    showFiles?: boolean;
    onSelect: (selected: string, dir: boolean) => void;
}

export default function SelectRemotePath(props: SelectRemotePathProps & JSX.IntrinsicAttributes & DialogProps) {
    let { initialPath, selectDir, showFiles } = props;

    if (showFiles === undefined) {
        showFiles = !selectDir;
    }

    const [paths, setPaths] = useState<Path[]>([]);
    const [separator, setSeparator] = useState<string>("\\");
    const [currentPath, setCurrentPath] = useState<string>(initialPath);
    const [lastClicked, setLastClicked] = useState<Path | undefined>();

    const [newDialogOpen, setNewDialogOpen] = useState(false);
    const [newFolderName, setNewFolderName] = useState<string>("");
    const [newFolderError, setNewFolderError] = useState<string>();

    const { t } = useTranslation();

    useEffect(() => {
        if (props.open)
            reloadPaths(initialPath);
    }, [initialPath, showFiles, props.open]);

    async function reloadPaths(dir: string) {
        const response = await triblerService.browseFiles(dir, showFiles || false);
        if (response === undefined) {
            toast.error(`${t("ToastErrorBrowseFiles")} ${t("ToastErrorGenNetworkErr")}`);
        } else if (isErrorDict(response)) {
            toast.error(`${t("ToastErrorBrowseFiles")} ${response.error.message}`);
        } else {
            setPaths(response.paths);
            setCurrentPath(response.current);
            setLastClicked((selectDir) ? { name: '', path: response.current, dir: true } : undefined);
            setSeparator(response.separator);
        }
    }

    return (
        <Dialog {...props}>
            <DialogContent className="max-w-3xl">
                <DialogHeader>
                    <DialogTitle>{selectDir ? t('PleaseSelectDirectory') : t('PleaseSelectFile')}</DialogTitle>
                    <DialogDescription className="text-base break-all">
                        {(currentPath || initialPath).split(separator).map((dir, index, array) => {
                            if (dir.length == 0 && index == 0) return <span key={index}>{separator}</span>
                            else if (dir.length == 0) return
                            return (
                                <span key={index}>
                                    <a className="cursor-pointer hover:text-black dark:hover:text-white"
                                        onClick={(event) => {
                                            let path = array.slice(0, index + 1).join(separator) + separator;
                                            reloadPaths(path)
                                            setLastClicked({
                                                name: dir,
                                                path,
                                                dir: true
                                            });
                                        }}>
                                        {dir}
                                    </a>
                                    {dir.endsWith(separator) ? "" : separator}
                                </span>
                            )
                        })}
                    </DialogDescription>
                </DialogHeader>

                <ScrollArea className="max-h-[380px] border">
                    <ContextMenu>
                        <ContextMenuTrigger>
                            <div className="flex-col">
                                {paths.map((item, index) => (
                                    <div
                                        className="p-2 hover:bg-accent border-x-1 [&:not(:first-child)]:border-t border-input flex cursor-pointer"
                                        key={index}
                                        onClick={(event) => {
                                            if (item.dir)
                                                reloadPaths(item.path)
                                            setLastClicked(item);
                                        }}
                                    >
                                        {item.dir && <Folder className="pr-2" />}
                                        {!item.dir && <FileIcon className="pr-2" />}
                                        <span className="break-all line-clamp-1">{item.name}</span>
                                    </div>
                                ))}
                            </div>
                        </ContextMenuTrigger>
                        <ContextMenuContent className="w-64 bg-neutral-50 dark:bg-neutral-950">
                            <ContextMenuItem
                                className="hover:bg-neutral-200 dark:hover:bg-neutral-800"
                                onClick={() => {
                                    setNewFolderName("");
                                    setNewFolderError(undefined);
                                    setNewDialogOpen(true);
                                }}>
                                <FolderPlus className="w-5 mx-2" />
                                {t('NewFolder')}..
                            </ContextMenuItem>
                        </ContextMenuContent>
                    </ContextMenu>
                </ScrollArea>

                <Dialog open={newDialogOpen} onOpenChange={setNewDialogOpen}>
                    <DialogContent>
                        <DialogHeader></DialogHeader>
                        <div className="py-2 flex items-center">
                            <Label htmlFor="new_folder" className="whitespace-nowrap pr-5">
                                {t('NewFolder')}
                            </Label>
                            <Input
                                id="new_folder"
                                className="col-span-5"
                                value={newFolderName}
                                onChange={(event) => setNewFolderName(event.target.value)}
                            />
                        </div>
                        {newFolderError !== undefined &&
                            <span className="text-center text-tribler text-sm">Error: {newFolderError}</span>
                        }
                        <DialogFooter>
                            <Button
                                variant="outline"
                                type="submit"
                                disabled={newFolderName.length < 1 || newFolderName.includes(separator)}
                                onClick={async () => {
                                    const newPath = [currentPath, newFolderName].join(separator);
                                    const response = await triblerService.createDirectory(newPath, true);
                                    if (!response || isErrorDict(response)) {
                                        setNewFolderError(!response ? "Unknown error" : response.error.message);
                                        return;
                                    }
                                    setNewFolderError(undefined);
                                    setNewDialogOpen(false);
                                    reloadPaths(currentPath);
                                }}>
                                {t('Create')}
                            </Button>
                            <DialogClose asChild>
                                <Button variant="outline" type="button">
                                    {t('Cancel')}
                                </Button>
                            </DialogClose>
                        </DialogFooter>
                    </DialogContent>
                </Dialog>

                <DialogFooter className="items-baseline">
                    {!selectDir && <p className="grow text-base break-all line-clamp-1">{lastClicked?.path || initialPath}</p>}
                    <Button
                        variant="outline"
                        type="submit"
                        onClick={() => {
                            if (props.onOpenChange)
                                props.onOpenChange(false);
                            if (lastClicked)
                                props.onSelect(lastClicked.path, lastClicked?.dir === true);
                        }}
                        disabled={!lastClicked || lastClicked.dir != selectDir}>
                        {t('Select')}
                    </Button>
                    <DialogClose asChild>
                        <Button variant="outline" type="button">
                            {t('Cancel')}
                        </Button>
                    </DialogClose>

                </DialogFooter>
            </DialogContent>
        </Dialog>
    )
}
