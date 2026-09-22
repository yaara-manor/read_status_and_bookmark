import { createFileRoute } from "@tanstack/react-router"

import { EventsService } from "@/client"
import { EventsTable } from "@/components/Events/EventsTable"

export const Route = createFileRoute("/_layout/bookmarked")({
  component: Bookmarked,
  head: () => ({
    meta: [
      {
        title: "Bookmarked - FastAPI Template",
      },
    ],
  }),
})

function Bookmarked() {
  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Bookmarked</h1>
        <p className="text-muted-foreground">Events you saved for later</p>
      </div>
      <EventsTable
        queryKey={["bookmarked"]}
        queryFn={async () => {
          const data = (
            await EventsService.readBookmarkedEvents({
              query: { skip: 0, limit: 100 },
            })
          ).data
          if (!data) {
            throw new Error("Bookmarked events missing")
          }
          return data
        }}
        emptyTitle="You don't have any bookmarks yet"
        emptyDescription="Bookmark an event from the Events page to see it here"
      />
    </div>
  )
}
