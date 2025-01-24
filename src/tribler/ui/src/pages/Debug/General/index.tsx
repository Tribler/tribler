import SimpleTable, { getHeader } from "@/components/ui/simple-table";
import { formatBytes } from "@/lib/utils";
import { KeyValue } from "@/models/keyvalue.model";
import { triblerService } from "@/services/tribler.service";
import { isErrorDict } from "@/services/reporting";
import { ColumnDef } from "@tanstack/react-table";
import { useCallback, useEffect, useState } from "react";
import { useInterval } from '@/hooks/useInterval';


const generalColumns: ColumnDef<KeyValue>[] = [
    {
        accessorKey: "key",
        header: getHeader("Key", false),
    },
    {
        accessorKey: "value",
        header: getHeader("Value", false),
    },
]

export default function General() {
    const [stats, setStats] = useState<KeyValue[]>([]);
    const [logs, setLogs] = useState<string>("");

    // The following three definitions are for the fancy scrolling-when-at-the-bottom effect of the logs
    const [shouldScrollDown, setShouldScrollDown] = useState<boolean>(true);
    const [logContainer, setLogContainer] = useState<HTMLElement | null>(null);
    const logContainerRef = useCallback((node: HTMLElement | null) => {
        if (shouldScrollDown && (node !== null)) {
            if (logContainer !== null)
                setShouldScrollDown(false);
            setLogContainer(node);
            node.scrollTop = node.scrollHeight;
        }
    }, [logs]);

    useInterval(async () => {
        const newStats = new Array<KeyValue>();

        const triblerStats = await triblerService.getTriblerStatistics();
        if (triblerStats === undefined || isErrorDict(triblerStats)) {
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
        if (ipv8Stats === undefined || isErrorDict(ipv8Stats)) {
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

        const logOutput = await triblerService.getLogs();
        if (logOutput !== undefined && !isErrorDict(logOutput)) {
            if (logContainer !== null)
                setShouldScrollDown(logContainer.scrollTop >= (logContainer.scrollHeight - logContainer.clientHeight));
            setLogs(logOutput);
        }
    }, 5000, true);

    return (
        <div className="w-full h-full flex flex-col">
            <SimpleTable data={stats} columns={generalColumns} />
            <div className="flex-none bg-neutral-100 dark:bg-neutral-900 text-muted-foreground border-y pl-3 py-2 text-sm font-medium">Logs</div>
            <div className="whitespace-pre-wrap overflow-x-auto text-xs pl-1 h-96 flex-grow overflow-scroll overflow-hidden scroll-smooth" ref={logContainerRef}>{logs}</div>
        </div>
    );
}
