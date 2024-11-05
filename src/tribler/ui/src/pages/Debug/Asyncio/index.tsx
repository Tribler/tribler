import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import Tasks from "./Tasks";
import Health from "./Health"
import SlowTasks from "./SlowTasks";


export default function IPv8() {
    return (
        <Tabs defaultValue="tasks" className="w-full flex flex-col flex-wrap">
            <TabsList className="flex-rows-3 border-b">
                <TabsTrigger value="tasks">Tasks</TabsTrigger>
                <TabsTrigger value="slow">Slow tasks</TabsTrigger>
                <TabsTrigger value="health">Health</TabsTrigger>
            </TabsList>
            <TabsContent value="tasks" className="contents">
                <Tasks />
            </TabsContent>
            <TabsContent value="slow">
                <SlowTasks />
            </TabsContent>
            <TabsContent value="health">
                <Health />
            </TabsContent>
        </Tabs>
     )
}