import SimpleTable from "@/components/ui/simple-table";
import { useState } from "react";
import { ipv8Service } from "@/services/ipv8.service";
import { Peer } from "@/models/tunnelpeer.model";
import { ColumnDef } from "@tanstack/react-table";
import { formatFlags } from "@/lib/utils";
import { useInterval } from '@/hooks/useInterval';


const peerColumns: ColumnDef<Peer>[] = [
    {
        accessorKey: "ip",
        header: "IP",
    },
    {
        accessorKey: "port",
        header: "Port",
    },
    {
        accessorKey: "mid",
        header: "Mid",
    },
    {
        accessorKey: "is_key_compatible",
        header: "Key compatible?",
    },
    {
        accessorKey: "flags",
        header: "Flags",
        cell: ({ row }) => {
            return <span>{formatFlags(row.original.flags)}</span>
        },
    },
]

export default function Peers() {
    const [peers, setPeers] = useState<Peer[]>([])

    useInterval(async () => {
        setPeers((await ipv8Service.getTunnelPeers()));
    }, 5000, true);

    return <SimpleTable data={peers} columns={peerColumns} />
}
