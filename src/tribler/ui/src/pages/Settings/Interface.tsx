import {DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger} from "@/components/ui/dropdown-menu";
import {Button} from "@/components/ui/button";
import {useTheme} from "@/contexts/ThemeContext";
import {FontFamilyIcon, FontSizeIcon} from "@radix-ui/react-icons";
import {useTranslation} from "react-i18next";

export default function Interface() {
    const {t} = useTranslation();
    const {fontFamily, fontSize, setFontFamily, setFontSize} = useTheme();

    const fonts = [
        {label: t("Default"), value: "system-ui, sans-serif"},
        {label: t("Arial"), value: "Arial, Helvetica, sans-serif"},
        {label: t("Courier New"), value: "'Courier New', Courier, monospace"},
        {label: t("Georgia"), value: "Georgia, serif"},
        {label: t("Impact"), value: "Impact, Charcoal, sans-serif"},
        {label: t("Lucida Console"), value: "'Lucida Console', Monaco, monospace"},
        {label: t("Tahoma"), value: "Tahoma, Verdana, sans-serif"},
        {label: t("Times New Roman"), value: "'Times New Roman', Times, serif"},
        {label: t("Trebuchet MS"), value: "'Trebuchet MS', Helvetica, sans-serif"},
        {label: t("Verdana"), value: "Verdana, Geneva, sans-serif"},
    ];

    const sizes = [
        {label: t("Small"), value: 14},
        {label: t("Default"), value: 16},
        {label: t("Large"), value: 20},
        {label: t("ExtraLarge"), value: 24},
    ];

    return (
        <div className="p-6 w-full">
            <div className="pb-4">
                <DropdownMenu>
                    <DropdownMenuTrigger asChild>
                        <Button variant="outline" size="sm" className="gap-2">
                            <FontFamilyIcon className="h-4 w-4" />
                            <span>
                                {t("FontType")} ({fonts.find((f) => f.value === fontFamily)?.label || t("Default")})
                            </span>
                        </Button>
                    </DropdownMenuTrigger>
                    <DropdownMenuContent align="start" className="w-56">
                        {fonts.map((font) => (
                            <DropdownMenuItem
                                key={font.value}
                                onClick={() => setFontFamily(font.value)}
                                className={fontFamily === font.value ? "bg-accent" : ""}>
                                <span style={{fontFamily: font.value}}>{font.label}</span>
                            </DropdownMenuItem>
                        ))}
                    </DropdownMenuContent>
                </DropdownMenu>
            </div>
            <div>
                <DropdownMenu>
                    <DropdownMenuTrigger asChild>
                        <Button variant="outline" size="sm" className="gap-2">
                            <FontSizeIcon className="h-4 w-4" />
                            <span>
                                {t("FontSize")} ({sizes.find((s) => s.value === fontSize)?.label || t("Default")})
                            </span>
                        </Button>
                    </DropdownMenuTrigger>
                    <DropdownMenuContent align="start" className="w-48">
                        {sizes.map((size) => (
                            <DropdownMenuItem
                                key={size.value}
                                onClick={() => setFontSize(size.value)}
                                className={fontSize === size.value ? "bg-accent" : ""}>
                                {size.label} ({size.value}px)
                            </DropdownMenuItem>
                        ))}
                    </DropdownMenuContent>
                </DropdownMenu>
            </div>
        </div>
    );
}
