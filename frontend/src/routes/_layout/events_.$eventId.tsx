import { useQuery, useQueryClient } from "@tanstack/react-query"
import { createFileRoute, useNavigate } from "@tanstack/react-router"
import { AxiosError } from "axios"
import { useEffect } from "react"
import { toast } from "sonner"

import { EventsService } from "@/client"
import { BookmarkToggle } from "@/components/Events/BookmarkToggle"
import { EventActionsMenu } from "@/components/Events/EventActionsMenu"

export const Route = createFileRoute("/_layout/events_/$eventId")({
  component: EventPage,
  head: () => ({
    meta: [
      {
        title: "Event - FastAPI Template",
      },
    ],
  }),
})

function EventPage() {
  const { eventId } = Route.useParams()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const {
    data: event,
    error,
    isPending,
  } = useQuery({
    queryKey: ["events", eventId],
    queryFn: async () => {
      const data = (await EventsService.readEvent({ path: { id: eventId } }))
        .data
      await queryClient.invalidateQueries({ queryKey: ["events"], exact: true })
      if (!data) {
        throw new Error("Event missing")
      }
      return data
    },
    retry: false,
  })

  const isMissing =
    error instanceof AxiosError &&
    [404, 422].includes(error.response?.status ?? 0)

  useEffect(() => {
    if (!isMissing) {
      return
    }
    toast.error("Event not found")
    void navigate({ to: "/events" })
  }, [isMissing, navigate])

  if (isPending || isMissing) {
    return <p className="text-muted-foreground">Loading...</p>
  }

  if (error || !event) {
    return <p className="text-muted-foreground">Something went wrong.</p>
  }

  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">{event.name}</h1>
          <p className="text-muted-foreground">
            {event.description || "No description"}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <BookmarkToggle event={event} />
          <EventActionsMenu
            event={event}
            onDeleted={() => navigate({ to: "/events" })}
          />
        </div>
      </div>
      <dl className="grid gap-4 text-sm">
        <div>
          <dt className="text-muted-foreground">ID</dt>
          <dd className="font-mono">{event.id}</dd>
        </div>
        <div>
          <dt className="text-muted-foreground">Time</dt>
          <dd>{event.time}</dd>
        </div>
        <div>
          <dt className="text-muted-foreground">Venue ID</dt>
          <dd className="font-mono">{event.venue_id}</dd>
        </div>
        <div>
          <dt className="text-muted-foreground">Performer ID</dt>
          <dd className="font-mono">{event.performer_id}</dd>
        </div>
        <div>
          <dt className="text-muted-foreground">Creator</dt>
          <dd>{event.creator}</dd>
        </div>
      </dl>
      <div>
        <h2 className="text-lg font-semibold">Tickets</h2>
        <ul className="mt-2 grid gap-1 text-sm text-muted-foreground">
          {event.tickets.map((ticket) => (
            <li key={ticket.id}>
              Row {ticket.row}, seat {ticket.seat}, {ticket.price},{" "}
              {ticket.availability}
            </li>
          ))}
        </ul>
      </div>
    </div>
  )
}
