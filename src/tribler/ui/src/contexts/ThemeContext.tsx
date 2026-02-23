import {triblerService} from "@/services/tribler.service";
import {createContext, useContext, useEffect, useState} from "react";

type Theme = "dark" | "light" | "system";

type ThemeProviderProps = {
    children: React.ReactNode;
    defaultTheme?: Theme;
    storageKey?: string;
};

type ThemeProviderState = {
    theme: Theme;
    fontFamily: string;
    fontSize: number;
    setTheme: (theme: Theme) => void;
    setFontFamily: (font: string) => void;
    setFontSize: (size: number) => void;
};

const initialState: ThemeProviderState = {
    theme: "system",
    fontFamily: "",
    fontSize: 0,
    setTheme: () => null,
    setFontFamily: () => null,
    setFontSize: () => null,
};

const ThemeProviderContext = createContext<ThemeProviderState>(initialState);

export function ThemeProvider({children, defaultTheme = "system", ...props}: ThemeProviderProps) {
    const [theme, setTheme] = useState<Theme>((triblerService.guiSettings.theme as Theme) ?? defaultTheme);
    const [fontFamily, setFontFamily] = useState<string>(triblerService.guiSettings.fontFamily || "");
    const [fontSize, setFontSize] = useState<number>(Number(triblerService.guiSettings.fontSize) || 0);

    useEffect(() => {
        const root = window.document.documentElement;

        root.classList.remove("light", "dark");
        const activeTheme =
            theme === "system" ? (window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light") : theme;
        root.classList.add(activeTheme);

        // Get default font family/size using getComputedStyle
        const style = getComputedStyle(root);
        root.style.setProperty("--user-font", fontFamily || style.fontFamily);
        root.style.setProperty("--user-font-size", `${fontSize || parseInt(style.fontSize)}px`);
    }, [theme, fontFamily, fontSize]);

    const value: ThemeProviderState = {
        theme,
        fontFamily,
        fontSize,
        setTheme: (newTheme) => {
            triblerService.setSettings({ui: {theme: newTheme}});
            setTheme(newTheme);
        },
        setFontFamily: (font) => {
            triblerService.setSettings({ui: {fontFamily: font}});
            setFontFamily(font);
        },
        setFontSize: (size) => {
            triblerService.setSettings({ui: {fontSize: size}});
            setFontSize(size);
        },
    };

    return (
        <ThemeProviderContext.Provider {...props} value={value}>
            {children}
        </ThemeProviderContext.Provider>
    );
}

export const useTheme = () => {
    const context = useContext(ThemeProviderContext);
    if (!context) throw new Error("useTheme must be used within a ThemeProvider");
    return context;
};
