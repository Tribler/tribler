import {useTranslation} from "react-i18next";
import {Tabs, TabsContent, TabsList, TabsTrigger} from "@/components/ui/tabs";
import Overlays from "./Overlays";
import Details from "./Details";

export default function IPv8() {
    const {t} = useTranslation();
    return (
        <Tabs defaultValue="overlays" className="w-full flex flex-col flex-wrap">
            <TabsList className="flex-rows-3 border-b">
                <TabsTrigger value="overlays">{t("Peers")}</TabsTrigger>
                <TabsTrigger value="details">{t("Traffic")}</TabsTrigger>
            </TabsList>
            <TabsContent value="overlays" className="w-full flex-grow flex-col focus-visible:ring-0">
                <Overlays />
            </TabsContent>
            <TabsContent value="details" className="contents">
                <Details />
            </TabsContent>
        </Tabs>
    );
}
