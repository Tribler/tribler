import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import Overlays from "./Overlays"
import Details from "./Details";


export default function IPv8() {
    return (
        <Tabs defaultValue="overlays" className="w-full flex flex-col flex-wrap">
            <TabsList className="flex-rows-3 border-b">
                <TabsTrigger value="overlays">Overlays</TabsTrigger>
                <TabsTrigger value="details">Details</TabsTrigger>
            </TabsList>
            <TabsContent value="overlays" className="w-full flex-grow flex-col focus-visible:ring-0">
                <Overlays />
            </TabsContent>
            <TabsContent value="details" className="contents">
                <Details />
            </TabsContent>
        </Tabs>
     )
}