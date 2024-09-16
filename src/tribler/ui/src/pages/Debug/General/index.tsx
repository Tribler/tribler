import SimpleTable from "@/components/ui/simple-table";
import { formatBytes } from "@/lib/utils";
import { KeyValue } from "@/models/keyvalue.model";
import { triblerService } from "@/services/tribler.service";
import { isErrorDict } from "@/services/reporting";
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
        const newStats = new Array<KeyValue>();

        const triblerStats = await triblerService.getTriblerStatistics();
        if (triblerStats === undefined || isErrorDict(triblerStats)){
            if (stats) {
                newStats.push({ key: 'Database size', value: stats.filter((entry) => entry.key == 'Database size')[0].value });
                newStats.push({ key: 'Number of torrents collected', value: stats.filter((entry) => entry.key == 'Number of torrents collected')[0].value });
            } else {
                newStats.push({ key: 'Database size', value: '?' });
                newStats.push({ key: 'Number of torrents collected', value: '?' });
            }
        } else {
            newStats.push({ key: 'Database size', value: formatBytes(triblerStats.db_size) });
            newStats.push({ key: 'Number of torrents collected', value: "" + triblerStats.num_torrents });
        }

        const ipv8Stats = await triblerService.getIPv8Statistics();
        if (ipv8Stats === undefined || isErrorDict(ipv8Stats)){
            if (stats) {
                newStats.push({ key: 'Total IPv8 bytes up', value: stats.filter((entry) => entry.key == 'Total IPv8 bytes up')[0].value });
                newStats.push({ key: 'Total IPv8 bytes down', value: stats.filter((entry) => entry.key == 'Total IPv8 bytes down')[0].value });
            } else {
                newStats.push({ key: 'Total IPv8 bytes up', value: '?' });
                newStats.push({ key: 'Total IPv8 bytes down', value: '?' });
            }
        } else {
            newStats.push({ key: 'Total IPv8 bytes up', value: formatBytes(ipv8Stats.total_up) });
            newStats.push({ key: 'Total IPv8 bytes down', value: formatBytes(ipv8Stats.total_down) });
        }

        setStats(newStats);
    }, 5000, true);

    return <SimpleTable data={stats} columns={generalColumns} />
}
