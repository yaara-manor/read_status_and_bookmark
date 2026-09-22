import { useMutation, useQueryClient } from "@tanstack/react-query"
import { Bookmark } from "lucide-react"

import { type EventPublic, type EventsPublic, EventsService } from "@/client"
import { Button } from "@/components/ui/button"
import { cn } from "@/lib/utils"

function patchList(
  old: EventsPublic | undefined,
  eventId: string,
  is_bookmarked: boolean,
) {
  if (!old?.data) {
    return old
  }
  return {
    ...old,
    data: old.data.map((row) =>
      row.id === eventId ? { ...row, is_bookmarked } : row,
    ),
  }
}

export function BookmarkToggle({ event }: { event: EventPublic }) {
  const queryClient = useQueryClient()
  const mutation = useMutation({
    mutationFn: (is_bookmarked: boolean) =>
      EventsService.setEventBookmark({
        path: { id: event.id },
        body: { is_bookmarked },
      }),
    onMutate: async (is_bookmarked) => {
      const previousEvents = queryClient.getQueryData<EventsPublic>(["events"])
      const previousEvent = queryClient.getQueryData<EventPublic>([
        "events",
        event.id,
      ])
      const previousBookmarked = queryClient.getQueryData<EventsPublic>([
        "bookmarked",
      ])
      if (previousEvents?.data) {
        queryClient.setQueryData(
          ["events"],
          patchList(previousEvents, event.id, is_bookmarked),
        )
      }
      if (previousEvent) {
        queryClient.setQueryData(["events", event.id], {
          ...previousEvent,
          is_bookmarked,
        })
      }
      if (previousBookmarked?.data) {
        if (!is_bookmarked) {
          const data = previousBookmarked.data.filter(
            (row) => row.id !== event.id,
          )
          queryClient.setQueryData(["bookmarked"], {
            ...previousBookmarked,
            data,
            count: data.length,
          })
        } else {
          queryClient.setQueryData(
            ["bookmarked"],
            patchList(previousBookmarked, event.id, true),
          )
        }
      }
      return { previousEvents, previousEvent, previousBookmarked }
    },
    onError: (_err, _vars, ctx) => {
      if (ctx?.previousEvents) {
        queryClient.setQueryData(["events"], ctx.previousEvents)
      }
      if (ctx?.previousEvent) {
        queryClient.setQueryData(["events", event.id], ctx.previousEvent)
      }
      if (ctx?.previousBookmarked) {
        queryClient.setQueryData(["bookmarked"], ctx.previousBookmarked)
      }
    },
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: ["events"] })
      queryClient.invalidateQueries({ queryKey: ["bookmarked"] })
    },
  })

  return (
    <Button
      data-testid="bookmark-toggle"
      type="button"
      variant="ghost"
      size="icon"
      className="relative z-10"
      aria-label={event.is_bookmarked ? "Remove bookmark" : "Bookmark"}
      aria-pressed={Boolean(event.is_bookmarked)}
      onClick={(e) => {
        e.stopPropagation()
        mutation.mutate(!event.is_bookmarked)
      }}
    >
      <Bookmark
        className={cn("size-4", event.is_bookmarked && "fill-current")}
      />
    </Button>
  )
}
