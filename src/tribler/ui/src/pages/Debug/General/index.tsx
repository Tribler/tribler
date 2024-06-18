import SimpleTable from "@/components/ui/simple-table";
import { formatBytes } from "@/lib/utils";
import { KeyValue } from "@/models/keyvalue.model";
import { triblerService } from "@/services/tribler.service";
import { ColumnDef } from "@tanstack/react-table";
import { useState } from "react";
import { useInterval } from '@/hooks/useInterval';


const generalColumns: ColumnDef<KeyValue>[] = [
    {
        accessorKey: "key",
        header: "Key",
    },
    {
        accessorKey: "value",
        header: "Value",
    },
]

export default function General() {
    const [stats, setStats] = useState<KeyValue[]>([])

    useInterval(async () => {
        const ipv8Stats = await triblerService.getIPv8Statistics();
        const triblerStats = await triblerService.getTriblerStatistics();
        setStats([
            { key: 'Database size', value: formatBytes(triblerStats.db_size) },
            { key: 'Number of torrents collected', value: triblerStats.num_torrents },
            { key: 'Total IPv8 bytes up', value: formatBytes(ipv8Stats.total_up) },
            { key: 'Total IPv8 bytes down', value: formatBytes(ipv8Stats.total_down) }
        ]);
    }, 5000, true);

    return <SimpleTable data={stats} columns={generalColumns} />
}
