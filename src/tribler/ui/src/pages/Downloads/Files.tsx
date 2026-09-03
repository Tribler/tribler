import toast from "react-hot-toast";
import {ColumnDef, Row} from "@tanstack/react-table";
import {FileTreeItem} from "@/models/file.model";
import {Download, StatusCode} from "@/models/download.model";
import {Dispatch, MutableRefObject, SetStateAction, useEffect, useMemo, useRef, useState} from "react";
import {isErrorDict} from "@/services/reporting";
import {triblerService} from "@/services/tribler.service";
import SimpleTable, {getHeader} from "@/components/ui/simple-table";
import {ChevronDown, ChevronRight, Gauge, Pause, Play} from "lucide-react";
import {Checkbox} from "@/components/ui/checkbox";
import {
    ContextMenu,
    ContextMenuContent,
    ContextMenuItem,
    ContextMenuSub,
    ContextMenuSubContent,
    ContextMenuSubTrigger,
    ContextMenuTrigger,
} from "@/components/ui/context-menu";
import {Slider} from "@/components/ui/slider";
import {filesToTree, formatBytes, getSelectedFilesFromTree} from "@/lib/utils";
import {useTranslation} from "react-i18next";

function toggleRowExpansion(e: React.MouseEvent<HTMLElement>, row: Row<FileTreeItem>) {
    (row.getToggleExpandedHandler() as (e: React.MouseEvent<HTMLElement>) => void)(e);
    // After this, the event is forwarded to the selection toggling logic.
    // We don't want to change the selection when expanding/collapsing. So, we stop it here.
    e.stopPropagation();
}

const getFileColumns = ({
    headers,
    onSelectedFiles,
}: {
    headers: any[];
    onSelectedFiles: (row: Row<FileTreeItem>) => void;
}): ColumnDef<FileTreeItem>[] => [
    {
        header: headers[0],
        accessorKey: "path",
        filterFn: (row, columnId, filterValue) => {
            return row.original.name.includes(filterValue);
        },
        cell: ({row}) => {
            return (
                <div
                    className="flex text-start items-center"
                    style={{
                        paddingLeft: `${row.depth * 2}rem`,
                    }}>
                    {row.original.subRows && row.original.subRows.length > 0 && (
                        <button onClick={(e) => {toggleRowExpansion(e, row)}}>
                            {row.getIsExpanded() ? (
                                <ChevronDown size="16" color="#777"></ChevronDown>
                            ) : (
                                <ChevronRight size="16" color="#777"></ChevronRight>
                            )}
                        </button>
                    )}
                    <span className="break-all line-clamp-1">{row.original.name}</span>
                </div>
            );
        },
    },
    {
        header: headers[1],
        accessorKey: "size",
        cell: ({row}) => {
            return (
                <div className="flex items-center">
                    <Checkbox
                        className="mr-2"
                        checked={row.original.included}
                        onCheckedChange={() => onSelectedFiles(row)}></Checkbox>
                    <span>{formatBytes(row.original.size)}</span>
                </div>
            );
        },
    },
    {
        header: headers[2],
        accessorKey: "progress",
        cell: ({row}) => {
            return <span>{((row.original.progress || 0) * 100).toFixed(1)}%</span>;
        },
    },
];

async function updateFiles(
    setFiles: Dispatch<SetStateAction<FileTreeItem[]>>,
    download: Download,
    initialized: MutableRefObject<boolean>
) {
    const response = await triblerService.getDownloadFiles(download.infohash);
    if (response !== undefined && !isErrorDict(response)) {
        const files = filesToTree(response, download.name, undefined, "/");
        setFiles(files);
    } else {
        // Don't bother the user on error, just try again later.
        initialized.current = false;
    }
}

function selectPaused(files: FileTreeItem[], selectedIndices: number[]): FileTreeItem[] {
    // A select change occurred while paused: only update the tree cache without syncing with the Tribler core!
    return files.map(fti => {
        return {
            ...fti,
            included: selectedIndices.includes(fti.index),
            subRows: selectPaused(fti.subRows || [], selectedIndices)
        };
    });
}

export default function Files({download, style}: {download: Download; style?: React.CSSProperties}) {
    const {t} = useTranslation();
    const [files, setFiles] = useState<FileTreeItem[]>([]);
    const [paused, setPaused] = useState<boolean>(false);
    const [changedWhilePaused, setChangedWhilePaused] = useState<boolean>(false);
    const [selectedFile, setSelectedFile] = useState<FileTreeItem | undefined>(undefined);
    const initialized = useRef(false);

    function OnSelectedFilesChange(row: Row<FileTreeItem>) {
        // Are we including or excluding files?
        const shouldInclude = row.original.included == false;
        // Get all indices that need toggling
        const toggleIndices = getSelectedFilesFromTree(row.original, !shouldInclude);
        const currentIndices = getSelectedFilesFromTree(files[0]);
        if (shouldInclude) var selectedIndices = [...new Set(currentIndices).union(new Set(toggleIndices))];
        else var selectedIndices = [...new Set(currentIndices).difference(new Set(toggleIndices))];

        if (!paused){
            triblerService.setDownloadFiles(download.infohash, selectedIndices).then((response) => {
                if (response === undefined) {
                    toast.error(`${t("ToastErrorDownloadSetFiles")} ${t("ToastErrorGenNetworkErr")}`);
                } else if (isErrorDict(response)) {
                    toast.error(`${t("ToastErrorDownloadSetFiles")} ${response.error.message}`);
                }
            });
            updateFiles(setFiles, download, initialized);
        } else {
            setChangedWhilePaused(true);
            setFiles(selectPaused(files, selectedIndices));
        }
    }

    useEffect(() => {
        // We just came out of pause and the user changed selected files.
        if (!paused && changedWhilePaused) {
            const selectedIndices = files.length > 0 ? getSelectedFilesFromTree(files[0]) : [];
            triblerService.setDownloadFiles(download.infohash, selectedIndices).then((response) => {
                if (response === undefined) {
                    toast.error(`${t("ToastErrorDownloadSetFiles")} ${t("ToastErrorGenNetworkErr")}`);
                } else if (isErrorDict(response)) {
                    toast.error(`${t("ToastErrorDownloadSetFiles")} ${response.error.message}`);
                }
            });
            setChangedWhilePaused(false);
        }
    }, [paused]);

    useEffect(() => {
        // Getting the files can take a lot of time, so we avoid doing this twice (due to StrictMode).
        if (initialized.current) {
            return;
        }
        initialized.current = true;
        updateFiles(setFiles, download, initialized);
    }, []);

    useEffect(() => {
        if (download.status_code === StatusCode.DOWNLOADING) updateFiles(setFiles, download, initialized);
    }, [download]);

    // Memoize the headers or column config will disappear when updating the list.
    const headers = [
        useMemo(() => getHeader("Path", true, true, true), []),
        useMemo(() => getHeader("Size"), []),
        useMemo(() => getHeader("Progress"), []),
    ];
    const fileColumns = getFileColumns({headers, onSelectedFiles: OnSelectedFilesChange});

    // The API call may not be finished yet or the download is still getting metainfo.
    if (files.length === 0) return <span className="flex pl-4 pt-2 text-muted-foreground">No files available</span>;

    return (
        <>
            <ContextMenu modal={false}>
                <ContextMenuTrigger>
                    <svg className="w-0 h-0">
                      <filter id="noise">
                        <feTurbulence type="turbulence" baseFrequency=".04" numOctaves="3" result="rawNoise">
                            <animate attributeName="seed" begin="0s" dur="8s" from="0" to="80" repeatCount="indefinite" />
                        </feTurbulence>
                        <feColorMatrix
                          in="rawNoise" result="colNoise"
                          type="matrix"
                          values="1 1 1 1 0
                                  .1 .1 .1 .1 0
                                  0 0 0 0 0
                                  0 0 0 .3 0" />
                        <feComposite in="SourceGraphic" in2="colNoise" mode="soft-light" />
                      </filter>
                    </svg>
                    <SimpleTable
                        data={files}
                        style={style}
                        className={paused ? "noise" : ""}
                        columns={fileColumns}
                        expandable={true}
                        storeSortingState="details-files-sorting"
                        allowSelect={true}
                        allowMultiSelect={false}
                        selectOnRightClick={true}
                        onSelectedRowsChange={(a) => {
                            if ((a.length == 1) && (a[0].included)) {
                                setSelectedFile(a[0]);
                            } else {
                                setSelectedFile(undefined);  // Can happen if we select a tree node instead of a file.
                            }
                        }}
                    />
                </ContextMenuTrigger>
                <ContextMenuContent className="w-64 bg-neutral-50 dark:bg-neutral-950">
                    <ContextMenuItem inset onClick={() => setPaused(!paused)}>
                        {paused ? <Play className="w-4 mx-2" /> : <Pause className="w-4 mx-2" />}
                        {paused ? t("UnpauseSelect") : t("PauseSelect")}
                    </ContextMenuItem>
                    <ContextMenuSub>
                        <ContextMenuSubTrigger
                            inset
                            disabled={selectedFile === undefined}
                            className={`${selectedFile === undefined ? "opacity-50" : ""}`}>
                            <Gauge className="w-4 mx-2" />
                            {t("Priority")}
                        </ContextMenuSubTrigger>
                        <ContextMenuSubContent className="w-48 bg-neutral-50 dark:bg-neutral-950 p-4">
                            <Slider defaultValue={[selectedFile?.priority || 4]} min={1} max={7} step={1}
                            onValueCommit={(v) => {
                                if (selectedFile !== undefined) {
                                    triblerService.setDownloadFilePriority(download.infohash, selectedFile.index, v[0]);
                                    setSelectedFile({...selectedFile, priority: v[0]});
                                    updateFiles(setFiles, download, initialized);
                                }
                            }}>
                            </Slider>
                        </ContextMenuSubContent>
                    </ContextMenuSub>
                </ContextMenuContent>
            </ContextMenu>
        </>
    );
}
