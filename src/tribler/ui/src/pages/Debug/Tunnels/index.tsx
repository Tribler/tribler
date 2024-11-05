import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import Circuits from "./Circuits"
import Relays from "./Relays"
import Exits from "./Exits"
import Swarms from "./Swarms"
import Peers from "./Peers"


export default function Tunnels() {
    return (
        <Tabs defaultValue="circuits" className="w-full flex flex-col">
            <TabsList className="flex-cols-5 border-b">
                <TabsTrigger value="circuits">Circuits</TabsTrigger>
                <TabsTrigger value="relays">Relays</TabsTrigger>
                <TabsTrigger value="exits">Exit sockets</TabsTrigger>
                <TabsTrigger value="swarms">Hidden swarms</TabsTrigger>
                <TabsTrigger value="peers">Peers</TabsTrigger>
            </TabsList>
            <TabsContent value="circuits" className="contents" >
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
    )
}
