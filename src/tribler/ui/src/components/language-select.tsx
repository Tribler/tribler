import { useLanguage } from "@/contexts/LanguageContext";
import { Button } from "./ui/button";
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from "./ui/dropdown-menu";
import { useTranslation } from "react-i18next";
import Cookies from "js-cookie";


const LanguageSelect = () => {
    const { language, setLanguage } = useLanguage();
    const { t, i18n } = useTranslation();

    const changeLanguage = (lng: string) => {
        setLanguage(lng);
        i18n.changeLanguage(lng);
        Cookies.set('lang', lng);
    };

    return (
        <DropdownMenu>
            <DropdownMenuTrigger asChild>
                <Button variant="ghost" className="h-8 w-8 p-0">
                    {language.slice(0, 2)}
                </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end" className="min-w-[6rem]">
                <DropdownMenuItem onClick={() => changeLanguage('en_US')}>
                    en
                </DropdownMenuItem>
                <DropdownMenuItem onClick={() => changeLanguage('es_ES')}>
                    es
                </DropdownMenuItem>
                <DropdownMenuItem onClick={() => changeLanguage('pt_BR')}>
                    pt
                </DropdownMenuItem>
                <DropdownMenuItem onClick={() => changeLanguage('ru_RU')}>
                    ru
                </DropdownMenuItem>
                <DropdownMenuItem onClick={() => changeLanguage('zh_CN')}>
                    zh
                </DropdownMenuItem>
            </DropdownMenuContent>
        </DropdownMenu>
    );
};

export default LanguageSelect;
