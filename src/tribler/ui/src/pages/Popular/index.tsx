import SimpleTable from "@/components/ui/simple-table";
import SaveAs from "@/dialogs/SaveAs";
import { useCallback, useEffect, useMemo, useState } from "react";
import { triblerService } from "@/services/tribler.service";
import { Torrent } from "@/models/torrent.model";
import { ColumnDef } from "@tanstack/react-table";
import { categoryIcon, filterDuplicates, formatBytes, formatTimeAgo, getMagnetLink, translateHeader } from "@/lib/utils";
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip";
import { useInterval } from '@/hooks/useInterval';


const getColumns = ({ onDownload }: { onDownload: (torrent: Torrent) => void }): ColumnDef<Torrent>[] => [
    {
        accessorKey: "category",
        header: "",
        cell: ({ row }) => {
            return (
                <TooltipProvider>
                    <Tooltip>
                        <TooltipTrigger><span>{categoryIcon(row.original.category)}</span></TooltipTrigger>
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
        header: translateHeader('Name'),
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
        header: translateHeader('Size'),
        cell: ({ row }) => {
            return <span className="whitespace-nowrap">{formatBytes(row.original.size)}</span>
        },
    },
    {
        accessorKey: "created",
        header: translateHeader('Created'),
        cell: ({ row }) => {
            return <span className="whitespace-nowrap">{formatTimeAgo(row.original.created)}</span>
        },
    },
]

export default function Popular() {
    const [open, setOpen] = useState<boolean>(false)
    const [torrents, setTorrents] = useState<Torrent[]>([])
    const [torrentDoubleClicked, setTorrentDoubleClicked] = useState<Torrent | undefined>();
    const [request, setRequest] = useState<string>("");

    useInterval(async () => {
        const popular = await triblerService.getPopularTorrents(true);
        setTorrents(filterDuplicates(popular, 'infohash'));
        const remoteQuery = await triblerService.searchTorrentsRemote('', true);
        setRequest(remoteQuery.request_uuid);
    }, 5000, true);

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
