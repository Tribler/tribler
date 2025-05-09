import { MoonIcon, SunIcon } from "@radix-ui/react-icons"

import { Button } from "@/components/ui/button"
import {
    DropdownMenu,
    DropdownMenuContent,
    DropdownMenuItem,
    DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"

import { EasyTooltip } from "./ui/tooltip"
import { useTranslation } from "react-i18next"
import { useTheme } from "@/contexts/ThemeContext"

export function ModeToggle() {
    const { t } = useTranslation();
    const { setTheme } = useTheme()

    return (
        <DropdownMenu>
            <EasyTooltip content={t('SelectTheme')}>
                <DropdownMenuTrigger asChild>
                    <span><Button variant="ghost" className="w-9 px-0">
                        <SunIcon className="h-[1.2rem] w-[1.2rem] rotate-0 scale-100 transition-all dark:-rotate-90 dark:scale-0" />
                        <MoonIcon className="absolute h-[1.2rem] w-[1.2rem] rotate-90 scale-0 transition-all dark:rotate-0 dark:scale-100" />
                        <span className="sr-only">Toggle theme</span>
                    </Button></span>
                </DropdownMenuTrigger>
            </EasyTooltip>
            <DropdownMenuContent align="end">
                <DropdownMenuItem className="cursor-pointer" onClick={() => setTheme("light")}>
                    Light
                </DropdownMenuItem>
                <DropdownMenuItem className="cursor-pointer" onClick={() => setTheme("dark")}>
                    Dark
                </DropdownMenuItem>
                <DropdownMenuItem className="cursor-pointer" onClick={() => setTheme("system")}>
                    System
                </DropdownMenuItem>
            </DropdownMenuContent>
        </DropdownMenu>
    )
}
