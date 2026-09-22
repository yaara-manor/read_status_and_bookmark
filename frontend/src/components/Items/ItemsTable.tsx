import { useSuspenseQuery } from "@tanstack/react-query"
import { useNavigate } from "@tanstack/react-router"
import { Search } from "lucide-react"
import { Suspense } from "react"

import type { ItemsPublic } from "@/client"
import { DataTable } from "@/components/Common/DataTable"
import PendingItems from "@/components/Pending/PendingItems"
import { columns } from "./columns"

type ItemsTableProps = {
  queryKey: readonly unknown[]
  queryFn: () => Promise<ItemsPublic>
  emptyTitle: string
  emptyDescription: string
}

function ItemsTableContent({
  queryKey,
  queryFn,
  emptyTitle,
  emptyDescription,
}: ItemsTableProps) {
  const { data: items } = useSuspenseQuery({ queryKey, queryFn })
  const navigate = useNavigate()

  if (items.data.length === 0) {
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
      data={items.data}
      onRowClick={(item) =>
        navigate({ to: "/items/$itemId", params: { itemId: item.id } })
      }
    />
  )
}

export function ItemsTable(props: ItemsTableProps) {
  return (
    <Suspense fallback={<PendingItems />}>
      <ItemsTableContent {...props} />
    </Suspense>
  )
}
