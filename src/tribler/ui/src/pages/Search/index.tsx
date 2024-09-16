import SimpleTable from "@/components/ui/simple-table";
import { useCallback, useEffect, useMemo, useState } from "react";
import { triblerService } from "@/services/tribler.service";
import { isErrorDict } from "@/services/reporting";
import { Torrent } from "@/models/torrent.model";
import { ColumnDef } from "@tanstack/react-table";
import { categoryIcon, filterDuplicates, formatBytes, formatTimeAgo, getMagnetLink } from "@/lib/utils";
import SaveAs from "@/dialogs/SaveAs";
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip";
import { useSearchParams } from "react-router-dom";
import { SwarmHealth } from "@/components/swarm-health";


const getColumns = ({ onDownload }: { onDownload: (torrent: Torrent) => void }): ColumnDef<Torrent>[] => [
    {
        accessorKey: "category",
        header: "",
        cell: ({ row }) => {
            return (
                <TooltipProvider>
                    <Tooltip>
                        <TooltipTrigger className="cursor-auto"><span>{categoryIcon(row.original.category)}</span></TooltipTrigger>
                        <TooltipContent>
                            {row.original.category}
                        </TooltipContent>
                    </Tooltip>
                </TooltipProvider>
            )
        },
    },
    {
        accessorKey: "name",
        header: "Name",
        cell: ({ row }) => {
            return <span
                className="inline-block cursor-pointer hover:underline line-clamp-1"
                onClick={() => onDownload(row.original)}>
                {row.original.name}
            </span>
        },
    },
    {
        accessorKey: "size",
        header: "Size",
        cell: ({ row }) => {
            return <span className="whitespace-nowrap">{formatBytes(row.original.size)}</span>
        },
    },
    {
        accessorKey: "num_seeders",
        header: "Health",
        cell: ({ row }) => {
            return <SwarmHealth torrent={row.original} />
        },
    },
    {
        accessorKey: "created",
        header: "Created",
        cell: ({ row }) => {
            return <span className="whitespace-nowrap">{formatTimeAgo(row.original.created)}</span>
        },
    },
]

export default function Search() {
    const [searchParams, setSearchParams] = useSearchParams();
    const query = searchParams.get("query");

    const [open, setOpen] = useState<boolean>(false)
    const [torrents, setTorrents] = useState<Torrent[]>([])
    const [torrentDoubleClicked, setTorrentDoubleClicked] = useState<Torrent | undefined>();
    const [request, setRequest] = useState<string>("");

    useEffect(() => {
        const searchTorrents = async () => {
            if (!query) return;
            const localResults = await triblerService.searchTorrentsLocal(query);
            if (!(localResults === undefined) && !isErrorDict(localResults)) {
                // Don't bother the user on error, just try again later.
                setTorrents(filterDuplicates(localResults, 'infohash'));
            }
            const remoteQuery = await triblerService.searchTorrentsRemote(query, false);
            if (!(remoteQuery === undefined) && !isErrorDict(remoteQuery)) {
                setRequest(remoteQuery.request_uuid);
            }
        }
        searchTorrents();
    }, [query]);

    useEffect(() => {
        (async () => { triblerService.addEventListener("torrent_health_updated", OnHealthEvent) })();
        return () => {
            (async () => { triblerService.removeEventListener("torrent_health_updated", OnHealthEvent) })();
        }
    }, []);

    const OnHealthEvent = (event: MessageEvent) => {
        const data = JSON.parse(event.data);
        setTorrents((prevTorrents) => prevTorrents.map((torrent: Torrent) => {
            if (torrent.infohash === data.infohash) {
                return {
                    ...torrent,
                    num_seeders: data.num_seeders,
                    num_leechers: data.num_leechers,
                    last_tracker_check: data.last_tracker_check
                }
            }
            return torrent;
        }));
    }

    useEffect(() => {
        (async () => { triblerService.addEventListener("remote_query_results", OnSearchEvent) })();
        return () => {
            (async () => { triblerService.removeEventListener("remote_query_results", OnSearchEvent) })();
        }
    }, [request]);

    const OnSearchEvent = (event: MessageEvent) => {
        const data = JSON.parse(event.data);
        if (data.uuid !== request)
            return;

        for (const result of data.results) {
            setTorrents((prevTorrents) => [...prevTorrents, result]);
        }
    }

    const handleDownload = useCallback((torrent: Torrent) => {
        setTorrentDoubleClicked(torrent);
        setOpen(true);
    }, []);

    const torrentColumns = useMemo(() => getColumns({ onDownload: handleDownload }), [handleDownload]);

    return (
        <>
            {torrentDoubleClicked &&
                <SaveAs
                    open={open}
                    onOpenChange={() => {
                        setTorrentDoubleClicked(undefined)
                        setOpen(false);
                    }}
                    uri={getMagnetLink(torrentDoubleClicked.infohash, torrentDoubleClicked.name)}
                />
            }
            <SimpleTable
                data={torrents}
                columns={torrentColumns}
            />
        </>
    )
}
