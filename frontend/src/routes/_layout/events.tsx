import { createFileRoute } from "@tanstack/react-router"

import { EventsService } from "@/client"
import AddEvent from "@/components/Events/AddEvent"
import { EventsTable } from "@/components/Events/EventsTable"

export const Route = createFileRoute("/_layout/events")({
  component: Events,
  head: () => ({
    meta: [
      {
        title: "Events - FastAPI Template",
      },
    ],
  }),
})

function Events() {
  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Events</h1>
          <p className="text-muted-foreground">Create and manage your events</p>
        </div>
        <AddEvent />
      </div>
      <EventsTable
        queryKey={["events"]}
        queryFn={async () => {
          const data = (
            await EventsService.readEvents({ query: { skip: 0, limit: 100 } })
          ).data
          if (!data) {
            throw new Error("Events missing")
          }
          return data
        }}
        emptyTitle="You don't have any events yet"
        emptyDescription="Add a new event to get started"
      />
    </div>
  )
}
