import { NavLink, useSearchParams } from "react-router-dom";
import { Icons } from "@/components/icons";
import { appConfig } from "@/config/app";
import { Button } from "@/components/ui/button";
import { ExitIcon } from "@radix-ui/react-icons";
import { ModeToggle } from "../mode-toggle";
import { Search } from "./Search";
import LanguageSelect from "../language-select";
import { triblerService } from "@/services/tribler.service";
import { useInterval } from "@/hooks/useInterval";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "../ui/dialog";
import { useEffect, useState } from "react";
import Cookies from "js-cookie";
import { DialogDescription } from "@radix-ui/react-dialog";
import { Ban  } from "lucide-react";

export function Header() {
    const [online, setOnline] = useState<boolean>(true);
    const [searchParams, setSearchParams] = useSearchParams();

    useEffect(() => {
        const key = searchParams.get("key");
        if (key) {
            const oldKey = Cookies.get("api_key");
            Cookies.set("api_key", key);
            searchParams.delete("key");
            setSearchParams(searchParams);
            if (key !== oldKey) {
                window.location.reload();
            }
        }
    }, [searchParams]);

    useInterval(() => {
        if (online !== triblerService.isOnline())
            setOnline(triblerService.isOnline());
    }, 1000);

    return (
        <>
            <Dialog open={!online}>
                <DialogContent
                    closable={false}
                    onInteractOutside={(e) => {
                        e.preventDefault();
                    }}
                >
                    <DialogHeader>
                        <DialogTitle className="flex items-center justify-center"><Ban className="inline mr-3"/>Failed to connect to Tribler</DialogTitle>
                        <DialogDescription className="text-center text-xs">Tribler may not be running or your browser is missing a cookie.<br />
                            In latter case please re-open Tribler from the system tray</DialogDescription>
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
                                onClick={() => triblerService.shutdown()}
                            >
                                <ExitIcon />
                            </Button>
                        </nav>
                    </div>
                </div>
            </header>
        </>
    )
}
