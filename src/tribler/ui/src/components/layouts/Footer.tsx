import { useInterval } from "@/hooks/useInterval";
import { formatBytes } from "@/lib/utils";
import { ipv8Service } from "@/services/ipv8.service";
import { isErrorDict } from "@/services/reporting";
import { triblerService } from "@/services/tribler.service";
import { DesktopIcon, DoubleArrowDownIcon, DoubleArrowUpIcon, GlobeIcon } from "@radix-ui/react-icons";
import { AxiosResponse } from "axios";
import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { EasyTooltip } from "../ui/tooltip";
import { TriblerStatistics } from "@/models/statistics.model";

export function Footer() {
    const { t } = useTranslation();

    const [statistics, setStatistics] = useState<TriblerStatistics>({ peers: 0, db_size: 0, num_torrents: 0 });
    const [speeds, setSpeeds] = useState({ up: 0, down: 0 });
    const [interactions, setInteractions] = useState(0);

    useInterval(async () => {
        let prevUp = statistics?.libtorrent?.total_sent_bytes || 0;
        let prevDown = statistics?.libtorrent?.total_recv_bytes || 0;

        let response = await triblerService.getTriblerStatistics();
        if (response && !isErrorDict(response)) {
            setStatistics(response);
            setSpeeds({
                up: ((response?.libtorrent?.total_sent_bytes || 0) - prevUp) / 5,
                down: ((response?.libtorrent?.total_recv_bytes || 0) - prevDown) / 5,
            });
        }
    }, 5000);

    useEffect(() => {
        const interceptor = (response: AxiosResponse) => {
            if (response.status >= 200 && response.status < 300) {
                setInteractions((n) => n + 1);
                setTimeout(() => {
                    setInteractions((n) => n - 1);
                }, 500);
            }
            return response;
        };
        triblerService.addResponseInterceptor(interceptor);
        ipv8Service.addResponseInterceptor(interceptor);
    }, []);

    return (
        <div className="border-t-[1px] border-neutral-300 dark:border-neutral-500 justify-items-end bottom-0">
            <div className="h-6 flex flex-row items-center">
                <div className="flex items-stretch"></div>

                <EasyTooltip content="Total BitTorrent download speed (including protocol overhead)">
                    <div className="flex items-center mx-1">
                        <DoubleArrowDownIcon className="w-4 mr-1" />
                        <span className="text-xs text-muted-foreground pr-1 select-none">
                            {formatBytes(speeds.down)}/s ({formatBytes(statistics?.libtorrent?.total_recv_bytes || 0)})
                        </span>
                    </div>
                </EasyTooltip>
                <p className="text-sm text-muted-foreground/50">|</p>
                <EasyTooltip content="Total BitTorrent upload speed (including protocol overhead)">
                    <div className="flex items-center mx-1">
                        <DoubleArrowUpIcon className="w-4 mr-1" />
                        <span className="text-xs text-muted-foreground pr-1 select-none">
                            {formatBytes(speeds.up)}/s ({formatBytes(statistics?.libtorrent?.total_sent_bytes || 0)})
                        </span>
                    </div>
                </EasyTooltip>
                <p className="text-sm text-muted-foreground/50">|</p>
                <EasyTooltip content={`Tribler peer connections: ${statistics?.peers}`}>
                    <div className="flex items-center mx-1">
                        {statistics?.peers >= 0 && statistics?.peers < 5 && (
                            <GlobeIcon color="#FF2D3F" className="w-4 mr-1" />
                        )}
                        {statistics?.peers >= 5 && statistics?.peers < 10 && (
                            <GlobeIcon color="#FFA72D" className="w-4 mr-1" />
                        )}
                        {statistics?.peers >= 10 && <GlobeIcon color="#83CD51" className="w-4 mr-1" />}
                    </div>
                </EasyTooltip>
                <p className="text-sm text-muted-foreground/50">|</p>
                <EasyTooltip content="Communication with Tribler backend">
                    <div className="flex items-center mx-1">
                        {interactions == 0 && <DesktopIcon color={undefined} className="w-4 mr-1" />}
                        {interactions != 0 && <DesktopIcon color="#567DD8" className="w-4 mr-1" />}
                    </div>
                </EasyTooltip>
            </div>
        </div>
    );
}
