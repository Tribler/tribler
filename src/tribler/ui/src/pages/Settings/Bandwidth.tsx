import {Icons} from "@/components/icons";
import {Button} from "@/components/ui/button";
import {Input} from "@/components/ui/input";
import {Label} from "@/components/ui/label";
import {Slider} from "@/components/ui/slider";
import {Settings} from "@/models/settings.model";
import {triblerService} from "@/services/tribler.service";
import {isErrorDict} from "@/services/reporting";
import {useEffect, useRef, useState} from "react";
import {useTranslation} from "react-i18next";
import toast from "react-hot-toast";
import SaveButton from "./SaveButton";
import {formatBytes} from "@/lib/utils";

import {
    CartesianGrid,
    DefaultTooltipContent,
    Line,
    LineChart,
    ResponsiveContainer,
    Tooltip,
    XAxis,
    YAxis,
} from "recharts";

interface AdvancedRateLimit {
    rate_up: number | null;
    rate_down: number | null;
    time: number;
}

/**
 * For each half hour in the day (48 points for 24 hours), create a AdvancedRateLimit instance.
 * The "time" is in hours, starting at 00:00. Ex.: 1.5 is 01:30 AM.
 */
function initChartData() {
    return Array.from({length: 48}, (e, i) => {
        return {rate_up: null, rate_down: null, time: i / 2};
    });
}

function getRateLimitsFor(settings: Settings, hops: string) {
    let rateSettings = settings?.libtorrent?.advanced_rate_limits;
    if (rateSettings && hops in rateSettings) {
        let limits = new Array<AdvancedRateLimit>();
        (JSON.parse(rateSettings[hops]) as [number | null, number | null][]).forEach((limit, i) => {
            limits.push({rate_up: limit[0], rate_down: limit[1], time: i / 2});
        });
        if (limits.length == 48)
            return limits;
    }
    return initChartData();
}

function formatRateLimits(data: {[key: string]: AdvancedRateLimit[]} | null) {
    let out: {[key: string]: string} = {};
    for (const key in data) {
        out[key] = JSON.stringify(data[key].map((e) => [e.rate_up, e.rate_down]));
    }
    return out;
}

export default function Bandwith() {
    const {t} = useTranslation();
    const [settings, setSettings] = useState<Settings>();
    const [data, setData] = useState<{[key: string]: AdvancedRateLimit[]} | null>(null);
    const [hops, setHops] = useState<number>(0);
    const lineChart = useRef<any>(null);
    const accordion = useRef<HTMLDivElement>(null);
    const [uploadSelected, setUploadSelected] = useState<boolean>(true);
    const [mouseDown, setMouseDown] = useState<boolean>(false);

    const hopsTranslations = [t("Metadata"), t("ZeroHops"), t("OneHop"), t("TwoHops"), t("ThreeHops")];

    useEffect(() => {
        (async () => {
            const response = await triblerService.getSettings();
            if (response === undefined) {
                toast.error(`${t("ToastErrorGetSettings")} ${t("ToastErrorGenNetworkErr")}`);
            } else if (isErrorDict(response)) {
                toast.error(`${t("ToastErrorGetSettings")} ${response.error.message}`);
            } else {
                setSettings(response);
                setData({
                    "-1": getRateLimitsFor(response, "-1"),
                    "0": getRateLimitsFor(response, "0"),
                    "1": getRateLimitsFor(response, "1"),
                    "2": getRateLimitsFor(response, "2"),
                    "3": getRateLimitsFor(response, "3"),
                });
                if (response?.libtorrent?.use_advanced_rate_limits && accordion.current) {
                    accordion.current.classList.add("renderadvanced");
                }
            }
        })();
    }, []);

    function handleEvent(event: React.MouseEvent<Element, MouseEvent>) {
        let chart = lineChart.current;
        if (chart === null || data === null) return;
        if (mouseDown || event.type == "mousedown") {
            const drawAreaHeight =
                chart.state.prevHeight -
                chart.state.offset.top -
                chart.state.offset.bottom;
            const pressedValue =
                (chart.state.yAxisMap[0].domain[1] *
                    (drawAreaHeight -
                        chart.state.activeCoordinate.y +
                        chart.props.margin.top -
                        1)) /
                drawAreaHeight;
            const newValue = event.buttons == 2 ? null : Math.max(1, Math.floor(pressedValue));
            const hopsKey = `${hops}`;
            setData({
                ...data,
                [hopsKey]: data[hopsKey].map((e) => {
                    return {
                        time: e.time,
                        rate_up: uploadSelected && e.time == chart.state.activeLabel ? newValue : e.rate_up,
                        rate_down:
                            !uploadSelected && e.time == chart.state.activeLabel ? newValue : e.rate_down,
                    };
                }),
            });
        }
    }

    function toggleAdvancedSettings() {
        if (accordion.current !== null)
            accordion.current.classList.toggle("renderadvanced");
        if (settings) {
            let mode = !(settings?.libtorrent?.use_advanced_rate_limits || false);
            setSettings({
                ...settings,
                libtorrent: {
                    ...settings.libtorrent,
                    use_advanced_rate_limits: mode,
                },
            });
        }
    }

    return (
        <div className="p-6 w-full">
            <div ref={accordion} id="accordion" className="group">
                <div className="rounded-t-lg border group-[.renderadvanced]:border-[#c96155] group-[:not(.renderadvanced)]:border-[#62c955] group-[.renderadvanced]:bg-muted group-[.renderadvanced]:text-muted-foreground inset-shadow-xs group-[:not(.renderadvanced)]:inset-shadow-[#62c955]">
                    <h2>
                        <button
                            className="relative flex w-full items-center border-0 px-5 py-4 text-left transition [overflow-anchor:none]"
                            type="button"
                            onClick={(e) => {
                                toggleAdvancedSettings();
                            }}>
                            <Icons.checkmark className="group-[.renderadvanced]:opacity-0 group-[:not(.renderadvanced)]:opacity-100 mr-4 transition-opacity duration-200 " />
                            <Icons.redcross className="group-[:not(.renderadvanced)]:opacity-0 group-[.renderadvanced]:opacity-100 absolute left-5 transition-opacity duration-200 " />
                            {t("SimpleSettings")}
                            <span className="-me-1 ms-auto h-5 w-5 shrink-0 rotate-[-180deg] transition-transform duration-200 ease-in-out group-[:not(.renderadvanced)]:me-0 group-[:not(.renderadvanced)]:rotate-0 motion-reduce:transition-none [&>svg]:h-6 [&>svg]:w-6">
                                <svg
                                    xmlns="http://www.w3.org/2000/svg"
                                    fill="none"
                                    viewBox="0 0 24 24"
                                    strokeWidth="1.5"
                                    stroke="currentColor">
                                    <path
                                        strokeLinecap="round"
                                        strokeLinejoin="round"
                                        d="M19.5 8.25l-7.5 7.5-7.5-7.5"
                                    />
                                </svg>
                            </span>
                        </button>
                    </h2>
                    <div
                        id="collapseOne"
                        className="!visible group-[.renderadvanced]:hidden border border-s-0 border-e-0 border-t-0 border-b-default">
                        <div className="grid grid-cols-3 gap-2 items-center p-4">
                            <Label htmlFor="max_upload_rate" className="whitespace-nowrap pr-5">
                                {t("UploadRate")}
                            </Label>
                            <Input
                                type="number"
                                id="max_upload_rate"
                                value={settings?.libtorrent ? settings?.libtorrent?.max_upload_rate / 1024 : 0}
                                onChange={(event) => {
                                    if (settings) {
                                        setSettings({
                                            ...settings,
                                            libtorrent: {
                                                ...settings.libtorrent,
                                                max_upload_rate: Math.max(0, +event.target.value) * 1024,
                                            },
                                        });
                                    }
                                }}
                            />
                            <Label htmlFor="max_upload_rate" className="whitespace-nowrap pr-5">
                                {t("RateUnit")}
                            </Label>

                            <Label htmlFor="max_download_rate" className="whitespace-nowrap pr-5">
                                {t("DownloadRate")}
                            </Label>
                            <Input
                                type="number"
                                id="max_download_rate"
                                value={settings?.libtorrent ? settings?.libtorrent?.max_download_rate / 1024 : 0}
                                onChange={(event) => {
                                    if (settings) {
                                        setSettings({
                                            ...settings,
                                            libtorrent: {
                                                ...settings.libtorrent,
                                                max_download_rate: Math.max(0, +event.target.value) * 1024,
                                            },
                                        });
                                    }
                                }}
                            />
                            <Label htmlFor="max_download_rate" className="whitespace-nowrap pr-5">
                                {t("RateUnit")}
                            </Label>
                            <p className="text-xs pt-2 pb-4 text-muted-foreground">{t("RateLimitNote")}</p>
                        </div>
                    </div>
                </div>

                <div className="border border-t-1  group-[.renderadvanced]:border-[#62c955] group-[:not(.renderadvanced)]:border-[#c96155] group-[:not(.renderadvanced)]:bg-muted group-[:not(.renderadvanced)]:text-muted-foreground inset-shadow-xs group-[.renderadvanced]:inset-shadow-[#62c955]">
                    <h2>
                        <button
                            className="relative flex w-full items-center border-0 px-5 py-4 text-left transition [overflow-anchor:none]"
                            type="button"
                            onClick={(e) => {
                                toggleAdvancedSettings();
                            }}>
                            <Icons.checkmark className="group-[.renderadvanced]:opacity-100 group-[:not(.renderadvanced)]:opacity-0 mr-4 transition-opacity delay-100 duration-200 " />
                            <Icons.redcross className="group-[:not(.renderadvanced)]:opacity-100 group-[.renderadvanced]:opacity-0 absolute left-5 transition-opacity delay-100 duration-200 " />
                            {t("AdvancedSettings")}
                            <span className="-me-1 ms-auto h-5 w-5 shrink-0 rotate-[-180deg] transition-transform duration-200 ease-in-out group-[.renderadvanced]:me-0 group-[.renderadvanced]:rotate-0 motion-reduce:transition-none [&>svg]:h-6 [&>svg]:w-6 ">
                                <svg
                                    xmlns="http://www.w3.org/2000/svg"
                                    fill="none"
                                    viewBox="0 0 24 24"
                                    strokeWidth="1.5"
                                    stroke="currentColor">
                                    <path
                                        strokeLinecap="round"
                                        strokeLinejoin="round"
                                        d="M19.5 8.25l-7.5 7.5-7.5-7.5"
                                    />
                                </svg>
                            </span>
                        </button>
                    </h2>

                    <div
                        id="collapseTwo"
                        className="!visible group-[:not(.renderadvanced)]:hidden w-full p-[2px]">
                        <div className="flex flex-cols-4 p-4">
                            <label>{t("Hops")}:</label>
                            <Slider
                                value={[hops]}
                                min={-1}
                                max={3}
                                step={1}
                                className="w-40 ml-4"
                                onValueChange={(value) => {
                                    setHops(value[0]);
                                }}
                            />
                            <label className="ml-2">{hopsTranslations[hops + 1]}</label>
                            <div className="flex-auto"> </div>
                            <label className="group w-60 h-8 bg-muted relative rounded-full select-none cursor-pointer flex ring-2 ml-4">
                                <input
                                    type="checkbox"
                                    className="peer appearance-none hidden"
                                    onChange={(e) => {
                                        setUploadSelected(!e.target.checked);
                                    }}
                                />
                                <div className="w-30 h-8 bg-[#F86F00] rounded-full shadow-[#F86F00] transition-all absolute left-0 group-hover:shadow-md/20 peer-checked:left-30"></div>
                                <span className="transition relative w-30 h-8 flex items-center justify-center text-muted peer-checked:text-primary text-xs">
                                    {t("UploadRate")}
                                </span>
                                <span className="transition relative w-30 h-8 flex items-center justify-center text-primary peer-checked:text-muted text-xs">
                                    {t("DownloadRate")}
                                </span>
                            </label>
                        </div>

                        <div
                            onMouseMove={handleEvent}
                            onMouseDown={(e) => {
                                setMouseDown(true);
                                handleEvent(e);
                            }}
                            onMouseUp={() => setMouseDown(false)}
                            onContextMenu={(e) => e.preventDefault()}
                            className="w-full grid place-items-center">
                            <ResponsiveContainer width="95%" aspect={3}>
                                <LineChart
                                    data={data === null ? undefined : data[`${hops}`]}
                                    ref={lineChart}
                                    margin={{top: 20, right: 10, left: 10, bottom: 5}}>
                                    <XAxis
                                        dataKey="time"
                                        tickFormatter={(tick) =>
                                            `${Math.floor(tick)}:` + `${60 * (tick % 1)}`.padStart(2, "0")
                                        }
                                        tick={{fill: "rgb(from hsl(var(--foreground)) r g b)"}}
                                    />
                                    <YAxis
                                        domain={[0, 100000000]}
                                        tickFormatter={(tick) => `${formatBytes(tick)}/s`}
                                        tick={{fill: "rgb(from hsl(var(--foreground)) r g b)"}}
                                    />
                                    <Tooltip
                                        cursor={{stroke: "var(--color-border-2)"}}
                                        contentStyle={{
                                            backgroundColor: "rgb(from hsl(var(--popover)) r g b)",
                                            borderColor: "var(--color-border-2)",
                                            color: "rgb(from hsl(var(--foreground)) r g b)",
                                        }}
                                        labelFormatter={(tick) =>
                                            `${Math.floor((tick % 13) + (tick >= 13 ? 1 : 0) + (tick < 1 ? 12 : 0))}:` +
                                            `${60 * (tick % 1)}`.padStart(2, "0") +
                                            ` ${tick >= 12 ? "P" : "A"}M`
                                        }
                                        formatter={(rate, lineName, props) => [
                                            `${formatBytes(rate as number)}/s`,
                                            (props.dataKey == "rate_up" ? t("UploadRate") : t("DownloadRate")) + ": ",
                                        ]}
                                        separator=""
                                        filterNull={false}
                                    />
                                    <CartesianGrid />
                                    <Line
                                        type="monotone"
                                        isAnimationActive={false}
                                        dataKey={uploadSelected ? "rate_up" : "rate_down"}
                                        name="&infin;"
                                        stroke="#F86F00"
                                    />
                                    <Line
                                        type="monotone"
                                        isAnimationActive={false}
                                        dataKey={uploadSelected ? "rate_down" : "rate_up"}
                                        name="&infin;"
                                        stroke="rgb(from hsl(var(--muted-foreground)) r g b)"
                                        activeDot={false}
                                    />
                                </LineChart>
                            </ResponsiveContainer>
                        </div>

                        <div className="w-full flex flex-row flex-wrap justify-center">
                            <Button
                                className="m-2"
                                onClick={(e) => {
                                    if (data !== null)
                                        setData({
                                            ...data,
                                            [`${hops}`]: data[`${hops}`].map((e) => {
                                                return {
                                                    rate_up: uploadSelected ? 1 : e.rate_up,
                                                    rate_down: uploadSelected ? e.rate_down : 1,
                                                    time: e.time,
                                                };
                                            }),
                                        });
                                }}>
                                MIN
                            </Button>
                            <Button
                                className="m-2"
                                onClick={(e) => {
                                    if (data !== null)
                                        setData({
                                            ...data,
                                            [`${hops}`]: data[`${hops}`].map((e) => {
                                                return {
                                                    rate_up: uploadSelected ? null : e.rate_up,
                                                    rate_down: uploadSelected ? e.rate_down : null,
                                                    time: e.time,
                                                };
                                            }),
                                        });
                                }}>
                                MAX
                            </Button>
                        </div>
                    </div>
                </div>
            </div>

            <SaveButton
                onClick={async () => {
                    if (settings) {
                        const response = await triblerService.setSettings({
                            ...settings,
                            libtorrent: {
                                ...settings.libtorrent,
                                advanced_rate_limits: formatRateLimits(data),
                            },
                        });
                        if (response === undefined) {
                            toast.error(`${t("ToastErrorSetSettings")} ${t("ToastErrorGenNetworkErr")}`);
                        } else if (isErrorDict(response)) {
                            toast.error(`${t("ToastErrorSetSettings")} ${response.error.message}`);
                        }
                    }
                }}
            />
        </div>
    );
}
