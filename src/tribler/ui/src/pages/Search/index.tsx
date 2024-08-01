import SimpleTable from "@/components/ui/simple-table";
import { useEffect, useState } from "react";
import { triblerService } from "@/services/tribler.service";
import { Torrent } from "@/models/torrent.model";
import { ColumnDef } from "@tanstack/react-table";
import { categoryIcon, filterDuplicates, formatBytes, formatTimeAgo, getMagnetLink } from "@/lib/utils";
import SaveAs from "@/dialogs/SaveAs";
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip";
import { useSearchParams } from "react-router-dom";
import { SwarmHealth } from "@/components/swarm-health";


const torrentColumns: ColumnDef<Torrent>[] = [
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
            return <span className="line-clamp-1">{row.original.name}</span>
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
            const localResults = await triblerService.searchTorrentsLocal(query, true);
            setTorrents(filterDuplicates(localResults, 'infohash'));
            const remoteQuery = await triblerService.searchTorrentsRemote(query, true);
            setRequest(remoteQuery.request_uuid);
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

    const OnDoubleClick = (torrent: Torrent) => {
        setTorrentDoubleClicked(torrent);
        setOpen(true);
    }

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
                onRowDoubleClick={(torrent) => { if (torrent) { OnDoubleClick(torrent) } }}
            />
        </>
    )
}
