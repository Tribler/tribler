import { triblerService } from "@/services/tribler.service"
import { createContext, useEffect, useState } from "react"

type ThemeProviderProps = {
    children: React.ReactNode
    defaultTheme?: string
    storageKey?: string
}

export type ThemeProviderState = {
    theme: string
    setTheme: (theme: string) => void
}

const initialState = {
    theme: "system",
    setTheme: () => null,
}

export const ThemeProviderContext = createContext<ThemeProviderState>(initialState)

export function ThemeProvider({
    children,
    defaultTheme = "system",
    storageKey = "shadcn-ui-theme",
    ...props
}: ThemeProviderProps) {
    const [theme, setTheme] = useState(triblerService.guiSettings.theme ?? defaultTheme);

    useEffect(() => {
        const root = window.document.documentElement

        root.classList.remove("light", "dark")

        if (theme === "system") {
            const systemTheme = window.matchMedia("(prefers-color-scheme: dark)")
                .matches
                ? "dark"
                : "light"

            root.classList.add(systemTheme)
            return
        }

        root.classList.add(theme)
    }, [theme])

    return (
        <ThemeProviderContext.Provider {...props} value={{
            theme,
            setTheme: (theme: string) => {
                triblerService.setSettings({ ui: { theme: theme } });
                setTheme(theme)
            },
        }}>
            {children}
        </ThemeProviderContext.Provider>
    )
}
