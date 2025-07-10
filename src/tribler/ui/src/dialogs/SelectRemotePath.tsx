import {useEffect, useMemo, useState} from "react";
import toast from "react-hot-toast";
import {triblerService} from "@/services/tribler.service";
import {isErrorDict} from "@/services/reporting";
import {
    Dialog,
    DialogClose,
    DialogContent,
    DialogDescription,
    DialogFooter,
    DialogHeader,
    DialogTitle,
} from "@/components/ui/dialog";
import {Button} from "@/components/ui/button";
import {DialogProps} from "@radix-ui/react-dialog";
import {JSX} from "react/jsx-runtime";
import {useTranslation} from "react-i18next";
import {Folder, File as FileIcon, FolderPlus} from "lucide-react";
import {Path} from "@/models/path.model";
import {ContextMenu, ContextMenuContent, ContextMenuItem, ContextMenuTrigger} from "@/components/ui/context-menu";
import {Label} from "@/components/ui/label";
import {Input} from "@/components/ui/input";
import SimpleTable, {getHeader} from "@/components/ui/simple-table";
import {ColumnDef, Row} from "@tanstack/react-table";

const getPathColumns = ({
    onClick,
    onNew,
}: {
    onClick: (row: Row<Path>) => void;
    onNew: () => void;
}): ColumnDef<Path>[] => [
    {
        accessorKey: "name",
        header: getHeader("Name", true, true, true),
        filterFn: (row, columnId, filterValue) => {
            // Don't remove the parent dir ("..") while filtering.
            return row.original.name.includes(filterValue) || row.original.name === "..";
        },
        cell: ({row}) => {
            const {t} = useTranslation();

            return (
                <ContextMenu>
                    <ContextMenuTrigger>
                        <div
                            className="flex text-start items-center cursor-pointer"
                            onClick={() => onClick(row)}
                            style={{
                                paddingLeft: `${row.depth * 2}rem`,
                            }}>
                            {row.original.dir && <Folder className="pr-2" />}
                            {!row.original.dir && <FileIcon className="pr-2" />}
                            <span className="break-all line-clamp-1">{row.original.name}</span>
                        </div>
                    </ContextMenuTrigger>
                    <ContextMenuContent className="w-64 bg-neutral-50 dark:bg-neutral-950">
                        <ContextMenuItem
                            className="hover:bg-neutral-200 dark:hover:bg-neutral-800"
                            onClick={() => onNew()}>
                            <FolderPlus className="w-5 mx-2" />
                            {t("NewFolder")}..
                        </ContextMenuItem>
                    </ContextMenuContent>
                </ContextMenu>
            );
        },
    },
];

interface SelectRemotePathProps {
    initialPath: string;
    selectDir: boolean;
    showFiles?: boolean;
    onSelect: (selected: string, dir: boolean) => void;
    filterFn?: (path: Path) => boolean;
}

export default function SelectRemotePath(props: SelectRemotePathProps & JSX.IntrinsicAttributes & DialogProps) {
    let {initialPath, selectDir, showFiles} = props;

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

    const {t} = useTranslation();

    useEffect(() => {
        if (props.open) reloadPaths(initialPath);
    }, [initialPath, showFiles, props.open]);

    async function reloadPaths(dir: string) {
        const response = await triblerService.browseFiles(dir, showFiles || false);
        if (response === undefined) {
            toast.error(`${t("ToastErrorBrowseFiles")} ${t("ToastErrorGenNetworkErr")}`);
        } else if (isErrorDict(response) && response.errorCode != 404) {
            toast.error(`${t("ToastErrorBrowseFiles")} ${response.error.message}`);
        } else if (isErrorDict(response)) {
            // If we couldn't get the requested path, browse the default path instead.
            let settings = await triblerService.getSettings();
            if (settings !== undefined && !isErrorDict(settings)) {
                let nextDir = settings.libtorrent.download_defaults.saveas;
                if (dir != nextDir) {
                    reloadPaths(nextDir);
                }
            }
        } else {
            let filterFn = props.filterFn;
            setPaths(filterFn ? response.paths.filter((path) => filterFn(path)) : response.paths);
            setCurrentPath(response.current);
            setLastClicked(selectDir ? {name: "", path: response.current, dir: true} : undefined);
            setSeparator(response.separator);
        }
    }

    function OnClick(row: Row<Path>) {
        if (row.original.dir) reloadPaths(row.original.path);
        setLastClicked(row.original);
    }
    function OnNew() {
        setNewFolderName("");
        setNewFolderError(undefined);
        setNewDialogOpen(true);
    }
    const pathColumns = useMemo(() => getPathColumns({onClick: OnClick, onNew: OnNew}), [OnClick, OnNew]);

    return (
        <Dialog {...props}>
            <DialogContent className="max-w-3xl">
                <DialogHeader>
                    <DialogTitle>{selectDir ? t("PleaseSelectDirectory") : t("PleaseSelectFile")}</DialogTitle>
                    <DialogDescription className="text-base break-all">
                        {(currentPath || initialPath).split(separator).map((dir, index, array) => {
                            if (dir.length == 0 && index == 0) return <span key={index}>{separator}</span>;
                            else if (dir.length == 0) return;
                            return (
                                <span key={index}>
                                    <a
                                        className="cursor-pointer hover:text-black dark:hover:text-white"
                                        onClick={(event) => {
                                            let path = array.slice(0, index + 1).join(separator) + separator;
                                            reloadPaths(path);
                                            setLastClicked({
                                                name: dir,
                                                path,
                                                dir: true,
                                            });
                                        }}>
                                        {dir}
                                    </a>
                                    {dir.endsWith(separator) ? "" : separator}
                                </span>
                            );
                        })}
                    </DialogDescription>
                </DialogHeader>

                <SimpleTable data={paths} columns={pathColumns} style={{maxHeight: 300}} />

                <Dialog open={newDialogOpen} onOpenChange={setNewDialogOpen}>
                    <DialogContent>
                        <DialogHeader></DialogHeader>
                        <div className="py-2 flex items-center">
                            <Label htmlFor="new_folder" className="whitespace-nowrap pr-5">
                                {t("NewFolder")}
                            </Label>
                            <Input
                                id="new_folder"
                                className="col-span-5"
                                value={newFolderName}
                                onChange={(event) => setNewFolderName(event.target.value)}
                            />
                        </div>
                        {newFolderError !== undefined && (
                            <span className="text-center text-tribler text-sm">Error: {newFolderError}</span>
                        )}
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
                                {t("Create")}
                            </Button>
                            <DialogClose asChild>
                                <Button variant="outline" type="button">
                                    {t("Cancel")}
                                </Button>
                            </DialogClose>
                        </DialogFooter>
                    </DialogContent>
                </Dialog>

                <DialogFooter className="items-baseline">
                    {!selectDir && (
                        <p className="grow text-base break-all line-clamp-1">{lastClicked?.path || initialPath}</p>
                    )}
                    <Button
                        variant="outline"
                        type="submit"
                        onClick={() => {
                            if (props.onOpenChange) props.onOpenChange(false);
                            if (lastClicked) props.onSelect(lastClicked.path, lastClicked?.dir === true);
                        }}
                        disabled={!lastClicked || lastClicked.dir != selectDir}>
                        {t("Select")}
                    </Button>
                    <DialogClose asChild>
                        <Button variant="outline" type="button">
                            {t("Cancel")}
                        </Button>
                    </DialogClose>
                </DialogFooter>
            </DialogContent>
        </Dialog>
    );
}
