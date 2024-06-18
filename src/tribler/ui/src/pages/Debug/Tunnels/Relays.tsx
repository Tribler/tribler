import SimpleTable from "@/components/ui/simple-table";
import { ColumnDef } from "@tanstack/react-table";
import { useState } from "react";
import { ipv8Service } from "@/services/ipv8.service";
import { Relay } from "@/models/relay.model";
import { formatBytes, formatTimeDiff } from "@/lib/utils";
import { useInterval } from '@/hooks/useInterval';


const relayColumns: ColumnDef<Relay>[] = [
    {
        accessorKey: "circuit_from",
        header: "From circuit",
    },
    {
        accessorKey: "circuit_to",
        header: "To circuit",
    },
    {
        accessorKey: "is_rendezvous",
        header: "Rendezvous?",
    },
    {
        accessorKey: "bytes_up",
        header: "Up",
        cell: ({ row }) => {
            return <span>{formatBytes(row.original.bytes_up)}</span>
        },
    },
    {
        accessorKey: "bytes_down",
        header: "Down",
        cell: ({ row }) => {
            return <span>{formatBytes(row.original.bytes_down)}</span>
        },
    },
    {
        accessorKey: "uptime",
        header: "Uptime",
        cell: ({ row }) => {
            return <span>{formatTimeDiff(row.original.creation_time)}</span>
        },
    },
]

export default function Relays() {
    const [relays, setRelays] = useState<Relay[]>([])

    useInterval(async () => {
        setRelays((await ipv8Service.getRelays()));
    }, 5000, true);

    return <SimpleTable data={relays} columns={relayColumns} />
}
