import { useSuspenseQuery } from "@tanstack/react-query"
import { useNavigate } from "@tanstack/react-router"
import { Search } from "lucide-react"
import { Suspense } from "react"

import type { EventsPublic } from "@/client"
import { DataTable } from "@/components/Common/DataTable"
import PendingEvents from "@/components/Pending/PendingEvents"
import { columns } from "./columns"

type EventsTableProps = {
  queryKey: readonly unknown[]
  queryFn: () => Promise<EventsPublic>
  emptyTitle: string
  emptyDescription: string
}

function EventsTableContent({
  queryKey,
  queryFn,
  emptyTitle,
  emptyDescription,
}: EventsTableProps) {
  const { data: events } = useSuspenseQuery({ queryKey, queryFn })
  const navigate = useNavigate()

  if (events.data.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center text-center py-12">
        <div className="rounded-full bg-muted p-4 mb-4">
          <Search className="h-8 w-8 text-muted-foreground" />
        </div>
        <h3 className="text-lg font-semibold">{emptyTitle}</h3>
        <p className="text-muted-foreground">{emptyDescription}</p>
      </div>
    )
  }

  return (
    <DataTable
      columns={columns}
      data={events.data}
      onRowClick={(event) =>
        navigate({ to: "/events/$eventId", params: { eventId: event.id } })
      }
    />
  )
}

export function EventsTable(props: EventsTableProps) {
  return (
    <Suspense fallback={<PendingEvents />}>
      <EventsTableContent {...props} />
    </Suspense>
  )
}
