import { useLanguage } from "@/contexts/LanguageContext";
import { Button } from "./ui/button";
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from "./ui/dropdown-menu";
import { useTranslation } from "react-i18next";
import { triblerService } from "@/services/tribler.service";
import { isErrorDict } from "@/services/reporting";
import { useEffect } from "react";
import toast from 'react-hot-toast';


const LanguageSelect = () => {
    const { language, setLanguage } = useLanguage();
    const { t, i18n } = useTranslation();

    useEffect(() => {
        const lng = triblerService.guiSettings.lang ?? 'en_US';
        setLanguage(lng);
        i18n.changeLanguage(lng);
    }, []);

    const changeLanguage = async (lng: string) => {
        setLanguage(lng);
        i18n.changeLanguage(lng);
        const response = await triblerService.setSettings({ ui: { lang: lng } });
        if (response === undefined) {
            toast.error(`${t("ToastErrorSetLanguage")} ${t("ToastErrorGenNetworkErr")}`);
        } else if (isErrorDict(response)){
            toast.error(`${t("ToastErrorSetLanguage")} ${response.error.message}`);
        }
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
                <DropdownMenuItem onClick={() => changeLanguage('ko_KR')}>
                    ko
                </DropdownMenuItem>

            </DropdownMenuContent>
        </DropdownMenu>
    );
};

export default LanguageSelect;
