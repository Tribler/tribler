import {useTranslation} from "react-i18next";
import {Tabs, TabsContent, TabsList, TabsTrigger} from "@/components/ui/tabs";
import Circuits from "./Circuits";
import Relays from "./Relays";
import Exits from "./Exits";
import Swarms from "./Swarms";
import Peers from "./Peers";

export default function Tunnels() {
    const {t} = useTranslation();
    return (
        <Tabs defaultValue="circuits" className="w-full flex flex-col">
            <TabsList className="flex-cols-5 border-b">
                <TabsTrigger value="circuits">{t("Circuits")}</TabsTrigger>
                <TabsTrigger value="relays">{t("Relays")}</TabsTrigger>
                <TabsTrigger value="exits">{t("ExitSockets")}</TabsTrigger>
                <TabsTrigger value="swarms">{t("HiddenSwarms")}</TabsTrigger>
                <TabsTrigger value="peers">{t("Peers")}</TabsTrigger>
            </TabsList>
            <TabsContent value="circuits" className="contents">
                <Circuits />
            </TabsContent>
            <TabsContent value="relays" className="contents">
                <Relays />
            </TabsContent>
            <TabsContent value="exits" className="contents">
                <Exits />
            </TabsContent>
            <TabsContent value="swarms" className="contents">
                <Swarms />
            </TabsContent>
            <TabsContent value="peers" className="contents">
                <Peers />
            </TabsContent>
        </Tabs>
    );
}
