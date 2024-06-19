import SimpleTable from "@/components/ui/simple-table";
import { useState } from "react";
import { ipv8Service } from "@/services/ipv8.service";
import { KeyValue } from "@/models/keyvalue.model";
import { ColumnDef } from "@tanstack/react-table";
import { useInterval } from '@/hooks/useInterval';


const statisticColumns: ColumnDef<KeyValue>[] = [
    {
        accessorKey: "key",
        header: "Key",
    },
    {
        accessorKey: "value",
        header: "Value",
        cell: ({ row }) => {
            return <span className="whitespace-pre">{row.original.value}</span>
        },
    },
]

export default function Statistics() {
    const [statistics, setStatistics] = useState<KeyValue[]>([])

    useInterval(async () => {
        let stats: KeyValue[] = [];
        for (const [key, value] of Object.entries(await ipv8Service.getDHTStatistics())) {
            stats.push({ key: key, value: (typeof value !== 'string') ? JSON.stringify(value, null, 4) : value });
        }
        setStatistics(stats);
    }, 5000, true);

    return <SimpleTable data={statistics} columns={statisticColumns} />
}
