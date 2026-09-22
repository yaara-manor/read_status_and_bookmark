import { createFileRoute } from "@tanstack/react-router"

import { ItemsService } from "@/client"
import { ItemsTable } from "@/components/Items/ItemsTable"

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
        <p className="text-muted-foreground">Items you saved for later</p>
      </div>
      <ItemsTable
        queryKey={["bookmarked"]}
        queryFn={async () =>
          (
            await ItemsService.readBookmarkedItems({
              query: { skip: 0, limit: 100 },
            })
          ).data
        }
        emptyTitle="You don't have any bookmarks yet"
        emptyDescription="Bookmark an item from the Items page to see it here"
      />
    </div>
  )
}
