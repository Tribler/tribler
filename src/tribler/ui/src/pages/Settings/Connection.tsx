import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectGroup, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Settings } from "@/models/settings.model";
import { triblerService } from "@/services/tribler.service";
import { isErrorDict } from "@/services/reporting";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import toast from 'react-hot-toast';
import SaveButton from "./SaveButton";


function injectOrUpdateIPv8If(entry: string, value: string, previous?: {interface: string, ip: string, port: number, worker_threads?: number}[]) {
    let updatedOrRemoved = false;
    let newIfs = [];
    if (!!previous){
        for (var e of previous){
            if (e.interface == entry){
                // If we had a previous entry:
                //  a. And now we have a new value: update!
                //  b. But now the entire interface is set to nothing: skip/remove!
                if (!!value)
                    newIfs.push({...e, ip: value});
                updatedOrRemoved = true;
            } else {
                // This wasn't modified, keep it.
                newIfs.push(e);
            }
        }
    }
    if ((!updatedOrRemoved) && (!!value)) {
        // We didn't update or remove, but we have a value set: add new!
        newIfs.push(
            {
                interface: entry,
                ip: value,
                port: (entry == "UDPIPv4") ? 8090 : 8091
            }
        );
    }
    return newIfs;
}


export default function Connection() {
    const { t } = useTranslation();
    const [settings, setSettings] = useState<Settings>();

    if (!settings) {
        (async () => {
            const response = await triblerService.getSettings();
            if (response === undefined) {
                toast.error(`${t("ToastErrorGetSettings")} ${t("ToastErrorGenNetworkErr")}`);
            } else if (isErrorDict(response)){
                toast.error(`${t("ToastErrorGetSettings")} ${response.error.message}`);
            } else {
                setSettings(response);
            }
        })();
        return null;
    }

    return (
        <div className="px-6 w-full">
            <div className="grid grid-cols-2 gap-2 items-center">
                <div className="pt-5 py-2 font-semibold col-span-2">{t('P2PSettings')}</div>

                <Label htmlFor="ipv8_ipv4" className="whitespace-nowrap pr-5">
                    {t('LocalListeningInterface') + " IPv4"}
                </Label>
                <Input
                    id="ipv8_ipv4"
                    value={settings?.ipv8?.interfaces.filter((e) => e.interface == "UDPIPv4")?.[0]?.ip}
                    onChange={(event) => {
                        if (settings) {
                            setSettings({
                                ...settings,
                                ipv8: {
                                    ...settings.ipv8,
                                    interfaces: injectOrUpdateIPv8If("UDPIPv4", event.target.value, settings?.ipv8?.interfaces)
                                }
                            });
                        }
                    }}
                />

                <Label htmlFor="ipv8_ipv6" className="whitespace-nowrap pr-5">
                    {t('LocalListeningInterface') + " IPv6"}
                </Label>
                <Input
                    id="ipv8_ipv6"
                    value={settings?.ipv8?.interfaces.filter((e) => e.interface == "UDPIPv6")?.[0]?.ip}
                    onChange={(event) => {
                        if (settings) {
                            setSettings({
                                ...settings,
                                ipv8: {
                                    ...settings.ipv8,
                                    interfaces: injectOrUpdateIPv8If("UDPIPv6", event.target.value, settings?.ipv8?.interfaces)
                                }
                            });
                        }
                    }}
                />

                <div className="pt-5 py-2 font-semibold col-span-2">{t('ProxySettings')}</div>

                <Label htmlFor="proxy_type" className="whitespace-nowrap pr-5">
                    {t('Type')}
                </Label>
                <Select
                    onValueChange={(value) => {
                        if (settings) {
                            setSettings({
                                ...settings,
                                libtorrent: {
                                    ...settings.libtorrent,
                                    proxy_type: +value
                                }
                            });
                        }
                    }}
                    value={settings?.libtorrent.proxy_type.toString()}
                    defaultValue="0"
                >
                    <SelectTrigger className="w-[180px]">
                        <SelectValue placeholder="Select a proxy type" />
                    </SelectTrigger>
                    <SelectContent>
                        <SelectGroup>
                            <SelectItem value="0">{t('None')}</SelectItem>
                            <SelectItem value="1">{t('Socks4')}</SelectItem>
                            <SelectItem value="2">{t('Socks5')}</SelectItem>
                            <SelectItem value="3">{t('Socks5Auth')}</SelectItem>
                            <SelectItem value="4">{t('HTTP')}</SelectItem>
                            <SelectItem value="5">{t('HTTPAuth')}</SelectItem>
                        </SelectGroup>
                    </SelectContent>
                </Select>

                <Label htmlFor="proxy_server" className="whitespace-nowrap pr-5">
                    {t('Server')}
                </Label>
                <Input
                    id="proxy_server"
                    value={settings?.libtorrent?.proxy_server.split(":")[0]}
                    onChange={(event) => {
                        if (settings) {
                            setSettings({
                                ...settings,
                                libtorrent: {
                                    ...settings.libtorrent,
                                    proxy_server: event.target.value + ':' + settings.libtorrent.proxy_server.split(":")[1]
                                }
                            });
                        }
                    }}
                />

                <Label htmlFor="proxy_port" className="whitespace-nowrap pr-5">
                    {t('Port')}
                </Label>
                <Input
                    id="proxy_port"
                    value={settings?.libtorrent?.proxy_server.split(":")[1]}
                    onChange={(event) => {
                        if (settings) {
                            setSettings({
                                ...settings,
                                libtorrent: {
                                    ...settings.libtorrent,
                                    proxy_server: settings.libtorrent.proxy_server.split(":")[0] + ':' + event.target.value
                                }
                            });
                        }
                    }}
                />

                <Label htmlFor="proxy_user" className="whitespace-nowrap pr-5">
                    {t('Username')}
                </Label>
                <Input
                    id="proxy_user"
                    value={settings?.libtorrent?.proxy_auth.split(":")[0]}
                    onChange={(event) => {
                        if (settings) {
                            setSettings({
                                ...settings,
                                libtorrent: {
                                    ...settings.libtorrent,
                                    proxy_auth: event.target.value + ':' + settings.libtorrent.proxy_auth.split(":")[1]
                                }
                            });
                        }
                    }}
                />

                <Label htmlFor="proxy_pass" className="whitespace-nowrap pr-5">
                    {t('Password')}
                </Label>
                <Input
                    id="proxy_pass"
                    value={settings?.libtorrent?.proxy_auth.split(":")[1]}
                    onChange={(event) => {
                        if (settings) {
                            setSettings({
                                ...settings,
                                libtorrent: {
                                    ...settings.libtorrent,
                                    proxy_auth: settings.libtorrent.proxy_auth.split(":")[0] + ':' + event.target.value
                                }
                            });
                        }
                    }}
                />


                <div className="pt-5 py-2 font-semibold col-span-2">{t('BittorrentFeatures')}</div>

                <Label htmlFor="libtorrent_ip" className="whitespace-nowrap pr-5">
                    {t('LocalListeningInterface')}
                </Label>
                <Input
                    id="libtorrent_ip"
                    value={settings?.libtorrent?.listen_interface}
                    onChange={(event) => {
                        if (settings) {
                            setSettings({
                                ...settings,
                                libtorrent: {
                                    ...settings.libtorrent,
                                    listen_interface: event.target.value
                                }
                            });
                        }
                    }}
                />

                <Label htmlFor="utp" className="whitespace-nowrap pr-5">
                    {t('EnableUTP')}
                </Label>
                <Checkbox
                    id="utp"
                    className="my-2"
                    checked={settings?.libtorrent.utp}
                    onCheckedChange={(value) => {
                        if (settings) {
                            setSettings({
                                ...settings,
                                libtorrent: {
                                    ...settings.libtorrent,
                                    utp: !!value
                                }
                            });
                        }
                    }}
                />

                <Label htmlFor="max_connections_download" className="whitespace-nowrap pr-5">
                    {t('MaxConnections')}
                </Label>
                <Input
                    id="max_connections_download"
                    type="number"
                    value={settings?.libtorrent?.max_connections_download}
                    onChange={(event) => {
                        if (settings) {
                            setSettings({
                                ...settings,
                                libtorrent: {
                                    ...settings.libtorrent,
                                    max_connections_download: Math.max(-1, +event.target.value)
                                }
                            });
                        }
                    }}
                />
                <div></div>
                <p className="text-xs p-0 pb-4 text-muted-foreground">{t('MinusOneIsUnlimited')}</p>

                <Label htmlFor="announce_to_all" className="whitespace-nowrap pr-5">
                    {t('EnableAnnounceAll')}
                </Label>
                <Checkbox
                    id="announce_to_all"
                    className="my-2"
                    checked={(settings?.libtorrent.announce_to_all_tiers !== settings?.libtorrent.announce_to_all_trackers) ? "indeterminate" : settings?.libtorrent.announce_to_all_tiers}
                    onCheckedChange={(value) => {
                        if (settings) {
                            setSettings({
                                ...settings,
                                libtorrent: {
                                    ...settings.libtorrent,
                                    announce_to_all_tiers: !!value,
                                    announce_to_all_trackers: !!value
                                }
                            });
                        }
                    }}
                />

                <Label htmlFor="max_concurrent_http_announces" className="whitespace-nowrap pr-5">
                    {t('MaxTrackerConnections')}
                </Label>
                <Input
                    id="max_concurrent_http_announces"
                    type="number"
                    value={settings?.libtorrent?.max_concurrent_http_announces === undefined ? 50 : settings?.libtorrent?.max_concurrent_http_announces}
                    onChange={(event) => {
                        if (settings) {
                            setSettings({
                                ...settings,
                                libtorrent: {
                                    ...settings.libtorrent,
                                    max_concurrent_http_announces: Math.max(1, +event.target.value)
                                }
                            });
                        }
                    }}
                />
            </div>

            <SaveButton
                onClick={async () => {
                    if (settings){
                        const response = await triblerService.setSettings(settings);
                        if (response === undefined) {
                            toast.error(`${t("ToastErrorSetSettings")} ${t("ToastErrorGenNetworkErr")}`);
                        } else if (isErrorDict(response)){
                            toast.error(`${t("ToastErrorSetSettings")} ${response.error.message}`);
                        }
                    }
                }}
            />
        </div>
    )
}
