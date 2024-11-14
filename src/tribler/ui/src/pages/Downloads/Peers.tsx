import { ColumnDef } from "@tanstack/react-table";
import { formatBytes } from "@/lib/utils";
import { Download } from "@/models/download.model";
import { Peer } from "@/models/bittorrentpeer.model";
import SimpleTable, { getHeader } from "@/components/ui/simple-table";


const peerFlags = (peer: Peer) => {
    let state = "";
    if (peer.optimistic) {
        state += "O,";
    }
    if (peer.uinterested) {
        state += "UI,";
    }
    if (peer.uchoked) {
        state += "UC,";
    }
    if (peer.uhasqueries) {
        state += "UQ,";
    }
    if (peer.uflushed) {
        state += "UBL,";
    }
    if (peer.dinterested) {
        state += "DI,";
    }
    if (peer.dchoked) {
        state += "DC,";
    }
    if (peer.snubbed) {
        state += "S,";
    }
    return state + peer['direction'];
}

const peerColumns: ColumnDef<Peer>[] = [
    {
        accessorKey: "ip",
        header: getHeader('PeerIpPort'),
        cell: ({ row }) => {
            return <span>{row.original.ip} ({row.original.port})</span>
        },
    },
    {
        accessorKey: "completed",
        header: getHeader('Completed'),
        cell: ({ row }) => {
            return <span>{(row.original.completed * 100).toFixed(0)}%</span>
        },
    },
    {
        accessorKey: "downrate",
        header: getHeader('SpeedDown'),
        cell: ({ row }) => {
            return <span>{formatBytes(row.original.downrate)}/s</span>
        },
    },
    {
        accessorKey: "uprate",
        header: getHeader('SpeedUp'),
        cell: ({ row }) => {
            return <span>{formatBytes(row.original.uprate)}/s</span>
        },
    },
    {
        accessorKey: "flags",
        header: getHeader('Flags'),
        cell: ({ row }) => {
            return <span>{peerFlags(row.original)}</span>
        },
    },
    {
        accessorKey: "extended_version",
        header: getHeader('Client'),
    },
]

export default function Peers({ download, height }: { download: Download, height?: string }) {
    if (!download.peers)
        return null;

    return <SimpleTable data={download.peers} columns={peerColumns} maxHeight={height}/>
}
