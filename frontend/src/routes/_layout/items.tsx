import { createFileRoute } from "@tanstack/react-router"

import { ItemsService } from "@/client"
import AddItem from "@/components/Items/AddItem"
import { ItemsTable } from "@/components/Items/ItemsTable"

export const Route = createFileRoute("/_layout/items")({
  component: Items,
  head: () => ({
    meta: [
      {
        title: "Items - FastAPI Template",
      },
    ],
  }),
})

function Items() {
  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Items</h1>
          <p className="text-muted-foreground">Create and manage your items</p>
        </div>
        <AddItem />
      </div>
      <ItemsTable
        queryKey={["items"]}
        queryFn={async () =>
          (await ItemsService.readItems({ query: { skip: 0, limit: 100 } }))
            .data
        }
        emptyTitle="You don't have any items yet"
        emptyDescription="Add a new item to get started"
      />
    </div>
  )
}
