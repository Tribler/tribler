import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectGroup, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Settings } from "@/models/settings.model";
import { triblerService } from "@/services/tribler.service";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import SaveButton from "./SaveButton";


export default function Connection() {
    const { t } = useTranslation();
    const [settings, setSettings] = useState<Settings>();

    if (!settings) (async () => { setSettings(await triblerService.getSettings()) })();

    return (
        <div className="px-6 w-full">
            <div className="grid grid-cols-2 gap-2 items-center">
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
                                    max_connections_download: Math.max(0, +event.target.value)
                                }
                            });
                        }
                    }}
                />
                <div></div>
                <p className="text-xs p-0 pb-4 text-muted-foreground">{t('ZeroIsUnlimited')}</p>
            </div>

            <SaveButton
                onClick={async () => {
                    if (settings)
                        await triblerService.setSettings(settings);
                }}
            />
        </div>
    )
}
