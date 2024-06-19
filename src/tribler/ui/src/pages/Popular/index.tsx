import SimpleTable from "@/components/ui/simple-table";
import SaveAs from "@/dialogs/SaveAs";
import { useState } from "react";
import { triblerService } from "@/services/tribler.service";
import { Torrent } from "@/models/torrent.model";
import { ColumnDef } from "@tanstack/react-table";
import { categoryIcon, formatBytes, formatTimeAgo, getMagnetLink, translateHeader } from "@/lib/utils";
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip";
import { useInterval } from '@/hooks/useInterval';


const torrentColumns: ColumnDef<Torrent>[] = [
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
            return <span className="line-clamp-1">{row.original.name}</span>
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

    useInterval(async () => {
        setTorrents((await triblerService.getPopularTorrents(true)));
    }, 5000, true);

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
