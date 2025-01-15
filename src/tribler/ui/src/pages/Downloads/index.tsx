import Actions from "./Actions";
import DownloadDetails from "./Details";
import SimpleTable, { getHeader } from "@/components/ui/simple-table"
import { Download } from "@/models/download.model";
import { Progress } from "@/components/ui/progress"
import { capitalize, formatBytes, formatDateTime, formatTimeRelative } from "@/lib/utils";
import { isErrorDict } from "@/services/reporting";
import { triblerService } from "@/services/tribler.service";
import { ColumnDef } from "@tanstack/react-table"
import { Card, CardHeader } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import {
    ResizableHandle,
    ResizablePanel,
    ResizablePanelGroup,
} from "@/components/ui/resizable"
import { useCallback, useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { useLocation } from "react-router-dom";
import { useInterval } from "@/hooks/useInterval";
import { usePrevious } from "@/hooks/usePrevious";
import { useResizeObserver } from "@/hooks/useResizeObserver";


export const filterAll = [1, 2, 3, 4, 5, 6, 7, 8, 9];
export const filterDownloading = [3];
export const filterCompleted = [4];
export const filterActive = [0, 1, 2, 3, 4, 7, 8, 9];
export const filterInactive = [5, 6];

const downloadColumns: ColumnDef<Download>[] = [
    {
        accessorKey: "name",
        minSize: 0,
        header: getHeader('Name'),
        cell: ({ row }) => {
            return <span className="break-all line-clamp-1">{row.original.name}</span>
        },
    },
    {
        accessorKey: "size",
        header: getHeader('Size'),
        cell: ({ row }) => {
            return <span>{formatBytes(row.original.size)}</span>
        },
    },
    {
        accessorKey: "progress",
        header: getHeader('Status'),
        cell: ({ row }) => {
            return (
                <div className="grid">
                    <div className="col-start-1 row-start-1">
                        <Progress className="h-5 bg-primary" value={row.original.progress * 100} indicatorColor="bg-tribler" />
                    </div>
                    <div className="col-start-1 row-start-1 text-white dark:text-black dark:font-mediumnormal text-center align-middle z-10">
                        {capitalize(row.original.status)} {(row.original.progress * 100).toFixed(0)}%
                    </div>
                </div>
            )
        },
    },
    {
        accessorKey: "num_seeds",
        header: getHeader('Seeds'),
        cell: ({ row }) => {
            return <span>{row.original.num_connected_seeds} ({row.original.num_seeds})</span>
        },
    },
    {
        accessorKey: "num_peers",
        header: getHeader('Peers'),
        cell: ({ row }) => {
            return <span>{row.original.num_connected_peers} ({row.original.num_peers})</span>
        },
    },
    {
        accessorKey: "speed_down",
        header: getHeader('SpeedDown'),
        cell: ({ row }) => {
            return <span>{formatBytes(row.original.speed_down)}/s</span>
        },
    },
    {
        accessorKey: "speed_up",
        header: getHeader('SpeedUp'),
        cell: ({ row }) => {
            return <span>{formatBytes(row.original.speed_up)}/s</span>
        },
    },
    {
        accessorKey: "hops",
        header: getHeader('Hops'),
    },
    {
        accessorKey: "eta",
        header: getHeader('ETA'),
        meta: {
            hide_by_default: true,
        },
        cell: ({ row }) => {
            if (row.original.progress === 1 || row.original.status_code !== 3)
                return <span>-</span>
            return <span>{formatTimeRelative(row.original.eta, false)}</span>
        },
    },
    {
        accessorKey: "time_added",
        header: getHeader('AddedOn'),
        meta: {
            hide_by_default: true,
        },
        cell: ({ row }) => {
            return <span>{formatDateTime(row.original.time_added)}</span>
        },
    },
]

export default function Downloads({ statusFilter }: { statusFilter: number[] }) {
    const { t } = useTranslation();
    const location = useLocation();

    const [filters, setFilters] = useState<{ id: string; value: string; }[]>([]);
    const [downloads, setDownloads] = useState<Download[]>([]);
    const [selectedDownloads, _setSelectedDownloads] = useState<Download[]>([]);

    const prevSelectedDownloads = usePrevious(selectedDownloads);
    const selectedDownloadsRef = useRef<Download[]>(selectedDownloads);
    // We need the useCallback hook here to avoid an infinite refresh loop
    const setSelectedDownloads = useCallback((data: Download[]) => {
        selectedDownloadsRef.current = data;
        _setSelectedDownloads(data);
    }, [_setSelectedDownloads]);

    useInterval(() => {
        updateDownloads();
    }, 5000);

    useEffect(() => {
        updateDownloads();
    }, [location]);

    useEffect(() => {
        // Refresh to avoid stale peers/pieces in the details panel.
        // We only refresh if the selection has changed due to a user action.
        if (!prevSelectedDownloads || (selectedDownloads.length === prevSelectedDownloads.length &&
            selectedDownloads.every((d, index) => d.infohash === prevSelectedDownloads[index].infohash))) {
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
        let infohash = (selectedDownloads.length === 1) ? selectedDownloads[0].infohash : '';
        if (infohashes)
            infohash = infohashes[0] ?? "";

        // Don't bother the user on error, just try again later.
        const response = await triblerService.getDownloads(infohash, !!infohash, !!infohash, !!infohash);
        if (response !== undefined && !isErrorDict(response)) {
            setDownloads(response.filter((download: Download) => {
                return statusFilter.includes(download.status_code);
            }));
        }
    }

    useEffect(() => {
        (async () => { triblerService.addEventListener("torrent_status_changed", OnEvent) })();
        return () => {
            (async () => { triblerService.removeEventListener("torrent_status_changed", OnEvent) })();
        }
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
    const parentRect = useResizeObserver({ element: document.querySelector('#download-list') });

    return (
        <ResizablePanelGroup direction="vertical" >
            <ResizablePanel defaultSize={75} className="min-h-[50px]" id="download-list">
                <div className="space-y-6 min-h-[200px]">
                    <Card className="border-none shadow-none">
                        <CardHeader className="md:flex-row md:justify-between space-y-0 items-center px-4 py-1.5">
                            <div className="flex flex-nowrap items-center">
                                <Actions selectedDownloads={selectedDownloads} />
                            </div>
                            <div>
                                <div className="flex items-center">
                                    <Input
                                        placeholder={t('FilterByName')}
                                        onChange={(event) => setFilters([{ id: 'name', value: event.target.value }])}
                                        className="max-w-sm"
                                    />
                                </div>
                            </div>
                        </CardHeader>
                        <SimpleTable
                            data={downloads}
                            columns={downloadColumns}
                            filters={filters}
                            allowMultiSelect={true}
                            onSelectedRowsChange={setSelectedDownloads}
                            maxHeight={Math.max((parentRect?.height ?? 50) - 50, 50)}
                            allowColumnToggle="download-columns"
                            storeSortingState="download-sorting"
                            rowId={(row) => row.infohash}
                        />
                    </Card>
                </div>
            </ResizablePanel>
            <ResizableHandle />
            <ResizablePanel defaultSize={25} className={`${selectedDownloads.length == 1 ? "flex" : "hidden"}`}>
                <DownloadDetails selectedDownloads={selectedDownloads} />
            </ResizablePanel>
        </ResizablePanelGroup>
    )
}
