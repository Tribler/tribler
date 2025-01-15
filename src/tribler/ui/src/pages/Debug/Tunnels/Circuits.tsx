import SimpleTable, { getHeader } from "@/components/ui/simple-table";
import { useState } from "react";
import { ipv8Service } from "@/services/ipv8.service";
import { isErrorDict } from "@/services/reporting";
import { Circuit } from "@/models/circuit.model";
import { ColumnDef } from "@tanstack/react-table";
import { formatBytes, formatFlags, formatTimeRelativeISO } from "@/lib/utils";
import { useInterval } from '@/hooks/useInterval';


const circuitColumns: ColumnDef<Circuit>[] = [
    {
        accessorKey: "circuit_id",
        header: getHeader("Circuit ID", false),
    },
    {
        accessorKey: "actual_hops",
        header: getHeader("Hops", false),
        cell: ({ row }) => {
            return <span>{row.original.actual_hops} / {row.original.goal_hops}</span>
        },
    },
    {
        accessorKey: "type",
        header: getHeader("Type", false),
    },
    {
        accessorKey: "state",
        header: getHeader("State", false),
    },
    {
        accessorKey: "bytes_up",
        header: getHeader("Up", false),
        cell: ({ row }) => {
            return <span>{formatBytes(row.original.bytes_up)}</span>
        },
    },
    {
        accessorKey: "bytes_down",
        header: getHeader("Down", false),
        cell: ({ row }) => {
            return <span>{formatBytes(row.original.bytes_down)}</span>
        },
    },
    {
        accessorKey: "uptime",
        header: getHeader("Uptime", false),
        cell: ({ row }) => {
            return <span>{formatTimeRelativeISO(row.original.creation_time)}</span>
        },
    },
    {
        accessorKey: "exit_flags",
        header: getHeader("Exit flags", false),
        cell: ({ row }) => {
            return <span>{formatFlags(row.original.exit_flags)}</span>
        },
    },
]

export default function Circuits() {
    const [circuits, setCircuits] = useState<Circuit[]>([])

    useInterval(async () => {
        const response = await ipv8Service.getCircuits();
        if (!(response === undefined) && !isErrorDict(response)) {
            // We ignore errors and correct with the missing information on the next call
            setCircuits(response);
        }
    }, 5000, true);

    return <SimpleTable data={circuits} columns={circuitColumns} />
}
