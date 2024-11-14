import SimpleTable, { getHeader } from "@/components/ui/simple-table";
import { Select, SelectContent, SelectGroup, SelectItem, SelectLabel, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { KeyValue } from "@/models/keyvalue.model";
import { triblerService } from "@/services/tribler.service";
import { isErrorDict } from "@/services/reporting";
import { ColumnDef } from "@tanstack/react-table";
import { useState } from "react";
import { useInterval } from '@/hooks/useInterval';


export const libtorrentColumns: ColumnDef<KeyValue>[] = [
    {
        accessorKey: "key",
        header: getHeader("Key", false),
    },
    {
        accessorKey: "value",
        header: getHeader("Value", false),
    },
]

export default function Libtorrent() {
    const [hops, setHops] = useState<number>(0)
    const [settings, setSettings] = useState<KeyValue[]>([])
    const [session, setSession] = useState<KeyValue[]>([])

    useInterval(async () => {
        const libtorrentSettings = await triblerService.getLibtorrentSettings(hops);
        if (!(libtorrentSettings === undefined) && !isErrorDict(libtorrentSettings)) {
            // Don't bother the user on error, just try again later.
            let settings = [];
            for (const [key, value] of Object.entries(libtorrentSettings)) {
                settings.push({ key: key, value: (typeof value !== 'string') ? JSON.stringify(value) : value });
            }
            setSettings(settings)
        }

        const libtorrentSession = await triblerService.getLibtorrentSession(hops);
        if (!(libtorrentSession === undefined) && !isErrorDict(libtorrentSession)) {
            // Don't bother the user on error, just try again later.
            let session = [];
            for (const [key, value] of Object.entries(libtorrentSession)) {
                session.push({ key: key, value: (typeof value !== 'string') ? JSON.stringify(value) : value });
            }
            setSession(session)
        }

    }, 5000, true);

    return (
        <Tabs defaultValue="settings" className="w-full flex flex-col flex-wrap">
            <TabsList className="flex-rows-4 border-b">
                <TabsTrigger value="settings">Settings</TabsTrigger>
                <TabsTrigger value="session">Session</TabsTrigger>
                <div className="flex items-center flex-1"></div>
                <div className="flex items-center pr-2">
                    <Select defaultValue="0" onValueChange={(hops) => setHops(Number(hops))}>
                        <SelectTrigger >
                            <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                            <SelectGroup>
                                <SelectLabel>Libtorrent session</SelectLabel>
                                <SelectItem value="0">Hops = 0</SelectItem>
                                <SelectItem value="1">Hops = 1</SelectItem>
                                <SelectItem value="2">Hops = 2</SelectItem>
                                <SelectItem value="3">Hops = 3</SelectItem>
                            </SelectGroup>
                        </SelectContent>
                    </Select>
                </div>
            </TabsList>
            <TabsContent value="settings" className="contents">
                <SimpleTable
                    data={settings}
                    columns={libtorrentColumns}
                />
            </TabsContent>
            <TabsContent value="session" className="contents">
                <SimpleTable
                    data={session}
                    columns={libtorrentColumns}
                />
            </TabsContent>
        </Tabs>
    )
}
