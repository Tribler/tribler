import {useTranslation} from "react-i18next";
import SimpleTable, {getHeader} from "@/components/ui/simple-table";
import {
    Select,
    SelectContent,
    SelectGroup,
    SelectItem,
    SelectLabel,
    SelectTrigger,
    SelectValue,
} from "@/components/ui/select";
import {Tabs, TabsContent, TabsList, TabsTrigger} from "@/components/ui/tabs";
import {KeyValue} from "@/models/keyvalue.model";
import {triblerService} from "@/services/tribler.service";
import {isErrorDict} from "@/services/reporting";
import {ColumnDef} from "@tanstack/react-table";
import {useState} from "react";
import {useInterval} from "@/hooks/useInterval";

export const libtorrentColumns: ColumnDef<KeyValue>[] = [
    {
        accessorKey: "key",
        header: getHeader("Key", true, true, true),
    },
    {
        accessorKey: "value",
        header: getHeader("Value"),
    },
];

export default function Libtorrent() {
    const {t} = useTranslation();
    const [hops, setHops] = useState<number>(0);
    const [settings, setSettings] = useState<KeyValue[]>([]);
    const [session, setSession] = useState<KeyValue[]>([]);

    useInterval(
        async () => {
            const libtorrentSettings = await triblerService.getLibtorrentSettings(hops);
            if (!(libtorrentSettings === undefined) && !isErrorDict(libtorrentSettings)) {
                // Don't bother the user on error, just try again later.
                let settings = [];
                for (const [key, value] of Object.entries(libtorrentSettings)) {
                    settings.push({key: key, value: typeof value !== "string" ? JSON.stringify(value) : value});
                }
                setSettings(settings);
            }

            const libtorrentSession = await triblerService.getLibtorrentSession(hops);
            if (!(libtorrentSession === undefined) && !isErrorDict(libtorrentSession)) {
                // Don't bother the user on error, just try again later.
                let session = [];
                for (const [key, value] of Object.entries(libtorrentSession)) {
                    session.push({key: key, value: typeof value !== "string" ? JSON.stringify(value) : value});
                }
                setSession(session);
            }
        },
        5000,
        true
    );

    return (
        <Tabs defaultValue="settings" className="w-full flex flex-col flex-wrap">
            <TabsList className="flex-rows-4 border-b">
                <TabsTrigger value="settings">{t("Settings")}</TabsTrigger>
                <TabsTrigger value="session">{t("Session")}</TabsTrigger>
                <div className="flex items-center flex-1"></div>
                <div className="flex items-center pr-2">
                    <Select defaultValue="0" onValueChange={(hops) => setHops(Number(hops))}>
                        <SelectTrigger>
                            <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                            <SelectGroup>
                                <SelectLabel>{t("LibtorrentSession")}</SelectLabel>
                                {[0, 1, 2, 3].map((hops) => (
                                    <SelectItem key={hops} value={String(hops)}>
                                        {t("SessionHops", {hops})}
                                    </SelectItem>
                                ))}
                                <SelectItem value="-1">{t("BackgroundTasks")}</SelectItem>
                            </SelectGroup>
                        </SelectContent>
                    </Select>
                </div>
            </TabsList>
            <TabsContent value="settings" className="contents">
                <SimpleTable
                    className="[&>[data-radix-scroll-area-viewport]]:max-h-[calc(100vh-122px)]"
                    data={settings}
                    columns={libtorrentColumns}
                />
            </TabsContent>
            <TabsContent value="session" className="contents">
                <SimpleTable
                    className="[&>[data-radix-scroll-area-viewport]]:max-h-[calc(100vh-122px)]"
                    data={session}
                    columns={libtorrentColumns}
                />
            </TabsContent>
        </Tabs>
    );
}
