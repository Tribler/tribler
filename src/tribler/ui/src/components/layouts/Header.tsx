import { NavLink, useSearchParams } from "react-router-dom";
import { Icons } from "@/components/icons";
import { appConfig } from "@/config/app";
import { Button } from "@/components/ui/button";
import { ExitIcon } from "@radix-ui/react-icons";
import { ModeToggle } from "../mode-toggle";
import { Search } from "./Search";
import LanguageSelect from "../language-select";
import { triblerService } from "@/services/tribler.service";
import { isErrorDict } from "@/services/reporting";
import { useInterval } from "@/hooks/useInterval";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "../ui/dialog";
import { useEffect, useRef, useState } from "react";
import toast, { Toaster } from 'react-hot-toast';
import Cookies from "js-cookie";
import { DialogDescription } from "@radix-ui/react-dialog";
import { Ban, Loader } from "lucide-react";
import { useTranslation } from "react-i18next";
import { ScrollArea } from "../ui/scroll-area";

export function Header() {
    const [online, setOnline] = useState<boolean>(true);
    const [shutdownLogs, setShutdownLogs] = useState<string[]>([]);
    const logsEndRef = useRef<null | HTMLDivElement>(null)
    const [searchParams, setSearchParams] = useSearchParams();
    const { t } = useTranslation();

    const scrollToBottom = () => {
        logsEndRef.current?.scrollIntoView({ behavior: "smooth" })
    }

    useEffect(() => {
        scrollToBottom()
    }, [shutdownLogs]);

    useEffect(() => {
        const key = searchParams.get("key");
        if (key) {
            const oldKey = Cookies.get("api_key");
            Cookies.set("api_key", key, { sameSite: 'strict' });
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
            if (!online)
                setShutdownLogs([]);
            setOnline(onlineNow);

        }
    }, 1000);

    useEffect(() => {
        (async () => {
            triblerService.addEventListener("tribler_shutdown_state", OnShutdownEvent) })();
            triblerService.getNewVersion().then(
                (result) => {
                    if (result && !isErrorDict(result)) toast(t("VersionAvailable") + ": " + result, {icon: "ℹ", });},
                (error) => {}
            );
        return () => {
            (async () => { triblerService.removeEventListener("tribler_shutdown_state", OnShutdownEvent) })();
        }
    }, []);

    const OnShutdownEvent = (event: MessageEvent) => {
        const data = JSON.parse(event.data);
        setShutdownLogs(prevLogs => [...prevLogs, data.state]);
    }

    return (
        <div className="h-fit">
            <Dialog open={!online || shutdownLogs.length > 0}>
                <DialogContent
                    closable={false}
                    onInteractOutside={(e) => {
                        e.preventDefault();
                    }}
                >
                    <DialogHeader>
                        <DialogTitle className="flex items-center justify-center mb-3">
                            {online ? <Loader className="inline mr-3 animate-[spin_3s_linear_infinite]" /> : <Ban className="inline mr-3" />}
                            {online
                                ? "Tribler is shutting down"
                                : (shutdownLogs.length > 0
                                    ? "Tribler has shutdown"
                                    : "Failed to connect to Tribler")}
                        </DialogTitle>

                        {!online && shutdownLogs.length === 0
                            ? <DialogDescription className="text-center text-xs">
                                Tribler may not be running or your browser is missing a cookie.
                                <br />In latter case please re-open Tribler from the system tray
                            </DialogDescription>
                            : <ScrollArea className="max-h-[380px]">
                                <DialogDescription className="text-xs font-mono">
                                    {shutdownLogs.map(log => <p>{log}<br /></p>)}
                                    <div ref={logsEndRef} />
                                </DialogDescription>
                            </ScrollArea>
                        }
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
                        <div className="w-full flex-1 md:w-auto md:flex-none">
                            {/* <CommandMenu /> */}
                        </div>
                        <nav className="flex items-center space-x-2">
                            <LanguageSelect />
                            <ModeToggle />
                            <Button
                                variant="ghost"
                                className="w-9 px-0"
                                onClick={() => {
                                    triblerService.shutdown().then((response) => {
                                        if (response === undefined) {
                                            toast.error(`${"ToastErrorShutdown"} ${"ToastErrorGenNetworkErr"}`);
                                        } else if (isErrorDict(response)){
                                            toast.error(`${"ToastErrorShutdown"} ${response.error.message}`);
                                        }
                                    })
                                }}
                            >
                                <ExitIcon />
                            </Button>
                        </nav>
                    </div>
                </div>
            </header>

            <Toaster
                position="bottom-left"
                toastOptions={{
                    className: 'bg-accent text-foreground font-light',
                }}
            />
        </div>
    )
}
