import {NavLink, useSearchParams} from "react-router-dom";
import {Icons} from "@/components/icons";
import {appConfig} from "@/config/app";
import {Button} from "@/components/ui/button";
import {ExitIcon, ReloadIcon} from "@radix-ui/react-icons";
import {ModeToggle} from "../mode-toggle";
import {Search} from "./Search";
import LanguageSelect from "../language-select";
import {triblerService} from "@/services/tribler.service";
import {isErrorDict} from "@/services/reporting";
import {useInterval} from "@/hooks/useInterval";
import {Dialog, DialogContent, DialogHeader, DialogTitle} from "../ui/dialog";
import {useEffect, useRef, useState} from "react";
import toast, {Toaster, ToastBar} from "react-hot-toast";
import Cookies from "js-cookie";
import {DialogDescription} from "@radix-ui/react-dialog";
import {Ban, Loader} from "lucide-react";
import type {TFunction} from "i18next";
import {useTranslation} from "react-i18next";
import {ScrollArea} from "../ui/scroll-area";
import {EasyTooltip} from "../ui/tooltip";

// Shutdown events carry human-readable messages from the core.
const shutdownMessages = new Map([
    ["Shutting down torrent checker.", "ShutdownTorrentChecker"],
    ["Shutting down IPv8 peer-to-peer overlays.", "ShutdownIPv8Overlays"],
    ["Shutting down download manager.", "ShutdownDownloadManager"],
    ["Shutting down local SOCKS5 interface.", "ShutdownSOCKS5"],
    ["Shutting down metadata database.", "ShutdownMetadataDatabase"],
    ["Shutting down GUI connection. Going dark.", "ShutdownGUIConnection"],
    ["Checkpointing Downloads...", "ShutdownCheckpointDownloads"],
    ["Shutting down Downloads...", "ShutdownDownloads"],
    ["Shutting down LibTorrent Manager...", "ShutdownLibtorrent"],
    ["Writing session state to disk.", "ShutdownWriteSession"],
    ["Stopping UPnP.", "ShutdownStopUPnP"],
    ["Removing temporary download files.", "ShutdownRemoveTempFiles"],
    ["Finished shutting down download manager.", "ShutdownDownloadManagerStopped"],
]);

function formatShutdownState(state: string, t: TFunction) {
    const key = shutdownMessages.get(state);
    if (key) return t(key);

    const waiting =
        /^Waiting for (\d+) downloads to finish\.(?:\.\.| (\d+) bytes left to write\.) (\d+\.\d{2}) seconds left until forced shutdown\.$/.exec(state);
    if (!waiting) return state;
    const [, downloads, bytes, seconds] = waiting;
    return t(bytes === undefined ? "ShutdownWaiting" : "ShutdownWaitingWithBytes", {
        downloads,
        bytes,
        seconds: Number(seconds),
        formatParams: {seconds: {minimumFractionDigits: 2}},
    });
}

export function Header() {
    const [online, setOnline] = useState<boolean>(true);
    const [shutdownLogs, setShutdownLogs] = useState<string[]>([]);
    const logsEndRef = useRef<null | HTMLDivElement>(null);
    const [searchParams, setSearchParams] = useSearchParams();
    const {t} = useTranslation();

    const scrollToBottom = () => {
        logsEndRef.current?.scrollIntoView({behavior: "smooth"});
    };

    useEffect(() => {
        scrollToBottom();
    }, [shutdownLogs]);

    useEffect(() => {
        const key = searchParams.get("key");
        if (key) {
            const oldKey = Cookies.get("api_key");
            Cookies.set("api_key", key, {sameSite: "strict"});
            searchParams.delete("key");
            setSearchParams(searchParams);
            if (key !== oldKey) {
                window.location.reload();
            }
        }
    }, [searchParams]);

    useInterval(() => {
        const onlineNow = triblerService.isOnline();
        if (online !== onlineNow) {
            if (!online) setShutdownLogs([]);
            setOnline(onlineNow);
        }
    }, 1000);

    useEffect(() => {
        (async () => {
            triblerService.addEventListener("tribler_shutdown_state", OnShutdownEvent);
        })();
        triblerService.getNewVersion().then(
            (result) => {
                if (result && !isErrorDict(result)) toast(t("VersionAvailable") + ": " + result, {icon: "ℹ"});
            },
            (error) => {}
        );
        return () => {
            (async () => {
                triblerService.removeEventListener("tribler_shutdown_state", OnShutdownEvent);
            })();
        };
    }, []);

    const OnShutdownEvent = (event: MessageEvent) => {
        const data = JSON.parse(event.data);
        setShutdownLogs((prevLogs) => [...prevLogs, data.state]);
    };

    return (
        <div className="h-fit">
            <Dialog open={!online || shutdownLogs.length > 0}>
                <DialogContent
                    closable={false}
                    onInteractOutside={(e) => {
                        e.preventDefault();
                    }}>
                    <DialogHeader>
                        <DialogTitle className="flex items-center justify-center mb-3">
                            {online ? (
                                <Loader className="inline mr-3 animate-[spin_3s_linear_infinite]" />
                            ) : (
                                <Ban className="inline mr-3" />
                            )}
                            {online
                                ? t("TriblerShuttingDown")
                                : shutdownLogs.length > 0
                                  ? t("TriblerShutDown")
                                  : t("ConnectionFailed")}
                        </DialogTitle>

                        {!online && shutdownLogs.length === 0 ? (
                            <DialogDescription className="whitespace-pre-line text-center text-xs">
                                {t("ConnectionFailedHelp")}
                            </DialogDescription>
                        ) : (
                            <ScrollArea className="max-h-[380px]">
                                <DialogDescription asChild={true} className="text-xs font-mono">
                                    <div>
                                        {shutdownLogs.map((log, idx) => (
                                            <div key={`shutdown-log-line-${idx}`}>
                                                {formatShutdownState(log, t)}
                                                <br />
                                            </div>
                                        ))}
                                        <div ref={logsEndRef} />
                                    </div>
                                </DialogDescription>
                            </ScrollArea>
                        )}
                    </DialogHeader>
                </DialogContent>
            </Dialog>

            <header className="sticky top-0 z-50 w-full border-b">
                <div className="container px-4 md:px-8 flex h-14 items-center">
                    <div className="mr-4 hidden md:flex">
                        <NavLink to="/" className="mr-6 flex items-center space-x-2">
                            <Icons.logo className="h-8 w-6 text-tribler pt-1" />
                            <span className="font-bold text-2xl text-tribler">{appConfig.name}</span>
                        </NavLink>
                    </div>
                    <a href="/" className="mr-6 flex items-center space-x-2 md:hidden">
                        <Icons.logo className="h-6 w-6" />
                        <span className="font-bold inline-block">{appConfig.name}</span>
                    </a>
                    <div className="container pt-2 px-4 md:px-8 flex h-14 items-stretch">
                        <Search />
                    </div>
                    {/* right */}
                    <div className="flex flex-1 items-center justify-between space-x-2 md:justify-end">
                        <div className="w-full flex-1 md:w-auto md:flex-none">{/* <CommandMenu /> */}</div>
                        <nav className="flex items-center space-x-2">
                            <LanguageSelect />
                            <ModeToggle />
                            <EasyTooltip content={t("Restart")}>
                                <Button
                                    aria-label={t("Restart")}
                                    variant="ghost"
                                    className="w-9 px-0"
                                    onClick={() => {
                                        triblerService.shutdown(true).then((response) => {
                                            if (response === undefined) {
                                                toast.error(
                                                    `${t("ToastErrorShutdown")} ${t("ToastErrorGenNetworkErr")}`
                                                );
                                            } else if (isErrorDict(response)) {
                                                toast.error(`${t("ToastErrorShutdown")} ${response.error.message}`);
                                            }
                                        });
                                    }}>
                                    <ReloadIcon />
                                </Button>
                            </EasyTooltip>
                            <EasyTooltip content={t("Shutdown")}>
                                <Button
                                    aria-label={t("Shutdown")}
                                    variant="ghost"
                                    className="w-9 px-0"
                                    onClick={() => {
                                        triblerService.shutdown(false).then((response) => {
                                            if (response === undefined) {
                                                toast.error(
                                                    `${t("ToastErrorShutdown")} ${t("ToastErrorGenNetworkErr")}`
                                                );
                                            } else if (isErrorDict(response)) {
                                                toast.error(`${t("ToastErrorShutdown")} ${response.error.message}`);
                                            }
                                        });
                                    }}>
                                    <ExitIcon />
                                </Button>
                            </EasyTooltip>
                        </nav>
                    </div>
                </div>
            </header>

            <Toaster
                position="bottom-left"
                toastOptions={{
                    className: "bg-accent text-foreground font-light",
                    duration: 15000
                }}
            >
            {(notification) => (
            <ToastBar toast={notification}>
              {({ icon, message }) => (
                <>
                  {icon}
                  {message}
                  <button
                     aria-label={t("Close")}
                     onClick={() => toast.dismiss(notification.id)}
                     className="text-muted-foreground hover:text-destructive">
                     <sup>✖</sup>
                  </button>
                </>
              )}
            </ToastBar>
          )}
        </Toaster>
        </div>
    );
}
