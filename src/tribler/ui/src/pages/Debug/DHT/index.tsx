import {useTranslation} from "react-i18next";
import {Tabs, TabsContent, TabsList, TabsTrigger} from "@/components/ui/tabs";
import Buckets from "./Buckets";
import Statistics from "./Statistics";

export default function DHT() {
    const {t} = useTranslation();
    return (
        <Tabs defaultValue="statistics" className="w-full flex flex-col">
            <TabsList className="flex-cols-2 border-b">
                <TabsTrigger value="statistics">{t("Statistics")}</TabsTrigger>
                <TabsTrigger value="buckets">{t("DHTBuckets")}</TabsTrigger>
            </TabsList>
            <TabsContent value="statistics" className="contents">
                <Statistics />
            </TabsContent>
            <TabsContent value="buckets" className="contents">
                <Buckets />
            </TabsContent>
        </Tabs>
    );
}
