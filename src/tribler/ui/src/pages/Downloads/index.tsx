import {ActionButtons, ActionMenu} from "./Actions";
import DownloadDetails from "./Details";
import SimpleTable, {getHeader} from "@/components/ui/simple-table";
import {Download, StatusCode} from "@/models/download.model";
import {capitalize, formatBytes, formatDateTime, formatTimeRelative} from "@/lib/utils";
import {isErrorDict} from "@/services/reporting";
import {triblerService} from "@/services/tribler.service";
import {ColumnDef} from "@tanstack/react-table";
import {Card, CardHeader} from "@/components/ui/card";
import {Input} from "@/components/ui/input";
import {ResizableHandle, ResizablePanel, ResizablePanelGroup} from "@/components/ui/resizable";
import {useCallback, useEffect, useRef, useState} from "react";
import {useTranslation} from "react-i18next";
import {useLocation} from "react-router-dom";
import {useInterval} from "@/hooks/useInterval";
import {usePrevious} from "@/hooks/usePrevious";
import {useResizeObserver} from "@/hooks/useResizeObserver";
import {ContextMenu, ContextMenuTrigger} from "@/components/ui/context-menu";
import {Button} from "@/components/ui/button";
import {XIcon} from "lucide-react";
import {EasyTooltip} from "@/components/ui/tooltip";

export const filterAll = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11];
export const filterDownloading = [3];
export const filterCompleted = [4];
export const filterActive = [0, 1, 2, 3, 4, 7, 8, 9, 10];
export const filterInactive = [5, 6, 11];

const downloadColumns: ColumnDef<Download>[] = [
    {
        accessorKey: "queue_position",
        header: getHeader("#", false, true, false),
        sortingFn: (rowA, rowB) => {
            if (rowA.original.hops < rowB.original.hops) return -1;
            if (rowA.original.hops > rowB.original.hops) return 1;
            return rowA.original.queue_position - rowB.original.queue_position;
        },
        cell: ({row}) => {
            const {t} = useTranslation();
            if (row.original.queue_position < 0) {
                return (
                    <EasyTooltip content={t("NotInQueue")}>
                        <span>*</span>
                    </EasyTooltip>
                );
            }
            return (
                <EasyTooltip
                    content={t("InQueue", {
                        hops: row.original.hops,
                        queue_position: row.original.queue_position + 1,
                    })}>
                    <span className="text-nowrap">{`${row.original.hops}-${row.original.queue_position + 1}`}</span>
                </EasyTooltip>
            );
        },
    },
    {
        accessorKey: "name",
        minSize: 0,
        header: getHeader("Name", true, true, true),
        cell: ({row}) => {
            return <span className="break-all line-clamp-1">{row.original.name}</span>;
        },
    },
    {
        accessorKey: "size",
        header: getHeader("Size"),
        cell: ({row}) => {
            return <span className="text-nowrap">{formatBytes(row.original.size)}</span>;
        },
    },
    {
        accessorKey: "all_time_upload",
        header: getHeader("TotalUp"),
        meta: {
            hide_by_default: true,
        },
        cell: ({row}) => {
            if (row.original.all_time_upload == 0) return <span>-</span>;
            return <span className="text-nowrap">{formatBytes(row.original.all_time_upload)}</span>;
        },
    },
    {
        accessorKey: "progress",
        header: getHeader("Status"),
        cell: ({row}) => {
            let status = `${capitalize(row.original.status.replaceAll("_", " "))} ${Math.floor(
                row.original.progress * 100
            )}%`;
            let progress = row.original.progress * 100;
            let color = "text-tribler";

            if (row.original.status_code == StatusCode.STOPPED_ON_ERROR) {
                status = "Error";
                progress = 100;
                color = "text-red-600";
            }

            return (
                <div className="grid">
                    <div className="col-start-1 row-start-1">
                        <Progress progress={progress} color={color} />
                    </div>
                    <div className="text-nowrap px-1 col-start-1 row-start-1 text-black dark:font-mediumnormal text-center align-middle">
                        {status}
                    </div>
                </div>
            );
        },
    },
    {
        accessorKey: "num_seeds",
        header: getHeader("Seeds"),
        cell: ({row}) => {
            const {t} = useTranslation();
            return (
                <EasyTooltip
                    content={[
                        t("ConnectedSeeders", {seeders: row.original.num_connected_seeds}),
                        t("UnconnectedSeeders", {seeders: row.original.num_seeds}),
                    ]}>
                    <span className="text-nowrap">
                        {row.original.num_connected_seeds} ({row.original.num_seeds})
                    </span>
                </EasyTooltip>
            );
        },
    },
    {
        accessorKey: "num_peers",
        header: getHeader("Peers"),
        cell: ({row}) => {
            const {t} = useTranslation();
            return (
                <EasyTooltip
                    content={[
                        t("ConnectedLeechers", {leechers: row.original.num_connected_peers}),
                        t("UnconnectedLeechers", {leechers: row.original.num_peers}),
                    ]}>
                    <span className="text-nowrap">
                        {row.original.num_connected_peers} ({row.original.num_peers})
                    </span>
                </EasyTooltip>
            );
        },
    },
    {
        accessorKey: "speed_down",
        header: getHeader("SpeedDown"),
        cell: ({row}) => {
            return <span className="text-nowrap">{formatBytes(row.original.speed_down)}/s</span>;
        },
    },
    {
        accessorKey: "speed_up",
        header: getHeader("SpeedUp"),
        cell: ({row}) => {
            return <span className="text-nowrap">{formatBytes(row.original.speed_up)}/s</span>;
        },
    },
    {
        accessorKey: "hops",
        header: getHeader("Hops"),
    },
    {
        accessorKey: "eta",
        header: getHeader("ETA"),
        meta: {
            hide_by_default: true,
        },
        cell: ({row}) => {
            if (row.original.progress === 1 || row.original.status_code !== StatusCode.DOWNLOADING)
                return <span>-</span>;
            return <span>{formatTimeRelative(row.original.eta, false)}</span>;
        },
    },
    {
        accessorKey: "last_upload",
        header: getHeader("LastUpload"),
        meta: {
            hide_by_default: true,
        },
        cell: ({row}) => {
            if (row.original.last_upload == 0) return <span>-</span>;
            return <span>{formatDateTime(row.original.last_upload)}</span>;
        },
    },
    {
        accessorKey: "time_added",
        header: getHeader("AddedOn"),
        meta: {
            hide_by_default: true,
        },
        cell: ({row}) => {
            return <span>{formatDateTime(row.original.time_added)}</span>;
        },
    },
    {
        accessorKey: "time_finished",
        header: getHeader("CompletedOn"),
        meta: {
            hide_by_default: true,
        },
        cell: ({row}) => {
            return <span>{row.original.time_finished > 0 ? formatDateTime(row.original.time_finished) : "-"}</span>;
        },
    },
];

function Progress({progress, color}: {progress: number; color: string}) {
    const ref = useRef<HTMLCanvasElement>(null);
    useEffect(() => {
        if (ref.current) {
            const canvas = ref.current.getContext("2d");
            if (!canvas) {
                return;
            }
            const width = canvas.canvas.width;
            const height = canvas.canvas.height;
            canvas.clearRect(0, 0, width, height);
            canvas.fillStyle = getComputedStyle(canvas.canvas).getPropertyValue("color");
            canvas.fillRect(0, 0, width * (progress / 100), height);
        }
    }, [progress]);
    return (
        <canvas
            ref={ref}
            className={`rounded-sm ${color}`}
            style={{height: "20px", width: "100%", background: "white", border: "1px solid #2f2f2f"}}
        />
    );
}

export default function Downloads({statusFilter}: {statusFilter: number[]}) {
    const {t} = useTranslation();
    const location = useLocation();

    const [filters, setFilters] = useState<{id: string; value: string}[]>([]);
    const [downloads, setDownloads] = useState<Download[]>([]);
    const [selectedDownloads, _setSelectedDownloads] = useState<Download[]>([]);

    const prevSelectedDownloads = usePrevious(selectedDownloads);
    const selectedDownloadsRef = useRef<Download[]>(selectedDownloads);
    // We need the useCallback hook here to avoid an infinite refresh loop
    const setSelectedDownloads = useCallback(
        (data: Download[]) => {
            selectedDownloadsRef.current = data;
            _setSelectedDownloads(data);
        },
        [_setSelectedDownloads]
    );

    useInterval(() => {
        updateDownloads();
    }, 5000);

    useEffect(() => {
        updateDownloads();
    }, [location]);

    useEffect(() => {
        // Refresh to avoid stale peers/pieces in the details panel.
        // We only refresh if the selection has changed due to a user action.
        if (
            !prevSelectedDownloads ||
            (selectedDownloads.length === prevSelectedDownloads.length &&
                selectedDownloads.every((d, index) => d.infohash === prevSelectedDownloads[index].infohash))
        ) {
            return;
        }
        updateDownloads();
    }, [selectedDownloads]);

    useEffect(() => {
        // Ensure selectedDownloads is updated. This should happen after updateDownloads finishes.
        const infohashes = selectedDownloads.map((download) => download.infohash);
        setSelectedDownloads(downloads.filter((download) => infohashes.includes(download.infohash)));
    }, [downloads]);

    async function updateDownloads(infohashes: string[] | undefined = undefined) {
        let infohash = selectedDownloads.length === 1 ? selectedDownloads[0].infohash : "";
        if (infohashes) infohash = infohashes[0] ?? "";

        // Don't bother the user on error, just try again later.
        const response = await triblerService.getDownloads(infohash, !!infohash, !!infohash, !!infohash);
        if (response !== undefined && !isErrorDict(response)) {
            setDownloads(
                response.filter((download: Download) => {
                    return statusFilter.includes(download.status_code);
                })
            );
        }
    }

    useEffect(() => {
        (async () => {
            triblerService.addEventListener("torrent_status_changed", OnEvent);
        })();
        return () => {
            (async () => {
                triblerService.removeEventListener("torrent_status_changed", OnEvent);
            })();
        };
    }, []);

    const OnEvent = (event: MessageEvent) => {
        // If the status of a selected download changes, update downloads immediately.
        const message = JSON.parse(event.data);
        const infohashes = selectedDownloadsRef.current.map((download) => download.infohash);
        if (infohashes.includes(message.infohash)) {
            // We need to use the infohashes from the ref or updateDownloads will run without the infohash filter
            updateDownloads(infohashes);
        }
    };

    // We're not getting resize event for elements within ResizeablePanel, so we track the ResizablePanel itself.
    const parentRect = useResizeObserver({element: document.querySelector("#download-list")});

    return (
        <ResizablePanelGroup direction="vertical">
            <ResizablePanel defaultSize={75} className="min-h-[50px]" id="download-list">
                <div className="space-y-6 min-h-[200px]">
                    <Card className="border-none shadow-none">
                        <CardHeader className="md:flex-row md:justify-between space-y-0 items-center px-4 py-1.5">
                            <div className="flex flex-nowrap items-center">
                                <ActionButtons
                                    selectedDownloads={selectedDownloads.filter(
                                        (d) => d.status_code !== StatusCode.LOADING
                                    )}
                                    onClick={() => setTimeout(updateDownloads, 100)}
                                />
                            </div>
                            <div>
                                <div className="relative w-full max-w-sm">
                                    <Input
                                        value={filters.find((filter) => filter.id == "name")?.value}
                                        placeholder={t("FilterByName")}
                                        onChange={(event) => setFilters([{id: "name", value: event.target.value}])}
                                        className="max-w-sm"
                                    />
                                    {filters.find((filter) => filter.id == "name")?.value && (
                                        <Button
                                            type="button"
                                            variant="ghost"
                                            size="icon"
                                            className="absolute right-1 top-1/2 -translate-y-1/2 h-7 w-7 text-gray-500
                                                   hover:text-gray-900 dark:text-gray-400 dark:hover:text-gray-100"
                                            onClick={() => setFilters([{id: "name", value: ""}])}>
                                            <XIcon className="h-4 w-4" />
                                            <span className="sr-only">Clear</span>
                                        </Button>
                                    )}
                                </div>
                            </div>
                        </CardHeader>

                        <ContextMenu modal={false}>
                            <ContextMenuTrigger>
                                <SimpleTable
                                    data={downloads}
                                    columns={downloadColumns}
                                    filters={filters}
                                    allowMultiSelect={true}
                                    onSelectedRowsChange={setSelectedDownloads}
                                    style={{
                                        maxHeight: (parentRect?.height ?? 50) - 50,
                                        height: (parentRect?.height ?? 50) - 50,
                                    }}
                                    allowColumnToggle="download-columns"
                                    storeSortingState="download-sorting"
                                    rowId={(row) => row.infohash}
                                    selectOnRightClick={true}
                                />
                            </ContextMenuTrigger>
                            <ActionMenu
                                selectedDownloads={selectedDownloads.filter(
                                    (d) => d.status_code !== StatusCode.LOADING
                                )}
                                onClick={() => setTimeout(updateDownloads, 100)}
                            />
                        </ContextMenu>
                    </Card>
                </div>
            </ResizablePanel>
            <ResizableHandle className={`${selectedDownloads.length == 1 ? "flex" : "hidden"}`} />
            <ResizablePanel defaultSize={25} className={`${selectedDownloads.length == 1 ? "flex" : "hidden"}`}>
                <DownloadDetails download={selectedDownloads.length > 0 ? selectedDownloads[0] : undefined} />
            </ResizablePanel>
        </ResizablePanelGroup>
    );
}
