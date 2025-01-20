import SimpleTable, { getHeader } from "@/components/ui/simple-table";
import { useCallback, useEffect, useMemo, useState } from "react";
import { triblerService } from "@/services/tribler.service";
import { isErrorDict } from "@/services/reporting";
import { Torrent } from "@/models/torrent.model";
import { ColumnDef } from "@tanstack/react-table";
import { categoryIcon, filterDuplicates, formatBytes, formatTimeRelative, getMagnetLink } from "@/lib/utils";
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
        header: getHeader("Name"),
        cell: ({ row }) => {
            return <span
                className="cursor-pointer hover:underline break-all line-clamp-1"
                onClick={() => onDownload(row.original)}>
                {row.original.name}
            </span>
        },
    },
    {
        accessorKey: "size",
        header: getHeader("Size"),
        cell: ({ row }) => {
            return <span className="whitespace-nowrap">{formatBytes(row.original.size)}</span>
        },
    },
    {
        accessorKey: "created",
        header: getHeader("Created"),
        cell: ({ row }) => {
            return (
                <span className="whitespace-nowrap">
                    {row.original.created > 24 * 3600 ?
                        formatTimeRelative(row.original.created) :
                        "unknown"}
                </span>
            )
        },
    },
    {
        accessorKey: "num_seeders",
        header: getHeader("Health"),
        cell: ({ row }) => {
            return <SwarmHealth torrent={row.original} />
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

        setTorrents((prevTorrents) => filterDuplicates([...prevTorrents, ...data.results], "infohash"));
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
                        if (query !== null)
                            triblerService.clickedResult(query, torrentDoubleClicked, torrents);
                        setTorrentDoubleClicked(undefined);
                        setOpen(false);
                    }}
                    uri={getMagnetLink(torrentDoubleClicked.infohash, torrentDoubleClicked.name)}
                />
            }
            <SimpleTable
                data={torrents}
                columns={torrentColumns}
                storeSortingState="search-sorting"
                rowId={(row) => row.infohash}
            />
        </>
    )
}
