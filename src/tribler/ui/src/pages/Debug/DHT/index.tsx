import {
    Tabs,
    TabsContent,
    TabsList,
    TabsTrigger,
} from "@/components/ui/tabs"
import Buckets from "./Buckets"
import Statistics from "./Statistics"


export default function DHT() {
    return (
        <Tabs defaultValue="statistics" className="w-full flex flex-col">
            <TabsList className="flex-cols-2 border-b">
                <TabsTrigger value="statistics">Statistics</TabsTrigger>
                <TabsTrigger value="buckets">Buckets</TabsTrigger>
            </TabsList>
            <TabsContent value="statistics" className="contents">
                <Statistics />
            </TabsContent>
            <TabsContent value="buckets" className="contents">
                <Buckets />
            </TabsContent>
        </Tabs>
     )
}