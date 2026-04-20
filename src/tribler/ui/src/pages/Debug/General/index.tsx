import SimpleTable, {getHeader} from "@/components/ui/simple-table";
import {formatBytes} from "@/lib/utils";
import {KeyValue} from "@/models/keyvalue.model";
import {triblerService} from "@/services/tribler.service";
import {isErrorDict} from "@/services/reporting";
import {ColumnDef} from "@tanstack/react-table";
import {useCallback, useState} from "react";
import {useInterval} from "@/hooks/useInterval";
import {ScrollArea} from "@/components/ui/scroll-area";
import {Pause, Play} from "lucide-react";
import {Button} from "@/components/ui/button";

const generalColumns: ColumnDef<KeyValue>[] = [
    {
        accessorKey: "key",
        header: getHeader("Key", false, true, true),
    },
    {
        accessorKey: "value",
        header: getHeader("Value", false),
    },
];

export default function General() {
    const [stats, setStats] = useState<KeyValue[]>([]);
    const [logs, setLogs] = useState<string>("");
    const [logSearch, setLogSearch] = useState<string>("");

    // The following three definitions are for the fancy scrolling-when-at-the-bottom effect of the logs
    const [shouldScrollDown, setShouldScrollDown] = useState<boolean>(true);
    const [logContainer, setLogContainer] = useState<HTMLElement | null>(null);
    const logContainerRef = useCallback(
        (node: HTMLElement | null) => {
            if (shouldScrollDown && node !== null) {
                if (logContainer !== null) setShouldScrollDown(false);
                setLogContainer(node);
                node.scrollTop = node.scrollHeight;
            }
        },
        [logs]
    );

    const [pauseLogs, setPauseLogs] = useState<boolean>(false);

    useInterval(
        async () => {
            const triblerStats = await triblerService.getTriblerStatistics();
            const ipv8Stats = await triblerService.getIPv8Statistics();

            if (
                triblerStats !== undefined &&
                !isErrorDict(triblerStats) &&
                ipv8Stats !== undefined &&
                !isErrorDict(ipv8Stats)
            ) {
                const newStats = new Array<KeyValue>();
                newStats.push({key: "Database size", value: formatBytes(triblerStats.db_size)});
                newStats.push({key: "Number of torrents collected", value: "" + triblerStats.num_torrents});
                newStats.push({key: "Endpoint version", value: "" + triblerStats.endpoint_version});
                newStats.push({key: "Total IPv8 bytes up", value: formatBytes(ipv8Stats.total_up)});
                newStats.push({key: "Total IPv8 bytes down", value: formatBytes(ipv8Stats.total_down)});
                setStats(newStats);
            }

            if (pauseLogs) return;

            const logOutput = await triblerService.getLogs();
            if (logOutput !== undefined && !isErrorDict(logOutput)) {
                if (logContainer !== null)
                    setShouldScrollDown(
                        logContainer.scrollTop >= logContainer.scrollHeight - logContainer.clientHeight
                    );
                setLogs(logOutput);
            }
        },
        5000,
        true
    );

    return (
        <div className="w-full h-full flex flex-col">
            <SimpleTable data={stats} columns={generalColumns} />
            <div className="flex-none bg-neutral-100 dark:bg-neutral-900 border-y pl-3 py-2 text-sm font-medium flex items-center">
                <span className="text-muted-foreground flex-none">Logs</span>
                <Button variant="ghost" className="h-4 w-4 ml-2 p-0 text-muted-foreground flex-none" onClick={() => setPauseLogs((pl) => !pl)}>
                    {pauseLogs ? <Play className="h-4 w-4" /> : <Pause className="h-4 w-4" />}
                </Button>
                <div className="flex-grow"></div>
                <input type="text" className="flex-none bg-background mr-2 border" placeholder="&#128269;" value={logSearch} onChange={(event) => {setLogSearch(event.target.value);}} />
            </div>
            <ScrollArea
                className="whitespace-pre-wrap break-all overflow-x-auto text-xs pl-3 h-96 flex-grow overflow-scroll overflow-hidden scroll-smooth"
                ref={logContainerRef}>
                {
                    (logSearch === "" || !logs.includes(logSearch)) ?
                        logs :
                    (logs.split(logSearch).map((part, i, parts) => {
                        if (i == parts.length - 1) return (<>{part}</>);
                        return (<>{part}<mark>{logSearch}</mark></>);
                    }))
                }
            </ScrollArea>
        </div>
    );
}
