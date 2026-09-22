import { useQuery, useQueryClient } from "@tanstack/react-query"
import { createFileRoute, useNavigate } from "@tanstack/react-router"
import { AxiosError } from "axios"
import { useEffect } from "react"
import { toast } from "sonner"

import { ItemsService } from "@/client"
import { BookmarkToggle } from "@/components/Items/BookmarkToggle"
import { ItemActionsMenu } from "@/components/Items/ItemActionsMenu"

export const Route = createFileRoute("/_layout/items_/$itemId")({
  component: ItemPage,
  head: () => ({
    meta: [
      {
        title: "Item - FastAPI Template",
      },
    ],
  }),
})

function ItemPage() {
  const { itemId } = Route.useParams()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const {
    data: item,
    error,
    isPending,
  } = useQuery({
    queryKey: ["items", itemId],
    queryFn: async () => {
      const data = (await ItemsService.readItem({ path: { id: itemId } })).data
      await queryClient.invalidateQueries({ queryKey: ["items"], exact: true })
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
    toast.error("Item not found")
    void navigate({ to: "/items" })
  }, [isMissing, navigate])

  if (isPending || isMissing) {
    return <p className="text-muted-foreground">Loading...</p>
  }

  if (error || !item) {
    return <p className="text-muted-foreground">Something went wrong.</p>
  }

  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">{item.title}</h1>
          <p className="text-muted-foreground">
            {item.description || "No description"}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <BookmarkToggle item={item} />
          <ItemActionsMenu
            item={item}
            onDeleted={() => navigate({ to: "/items" })}
          />
        </div>
      </div>
      <dl className="grid gap-4 text-sm">
        <div>
          <dt className="text-muted-foreground">ID</dt>
          <dd className="font-mono">{item.id}</dd>
        </div>
        <div>
          <dt className="text-muted-foreground">Creator</dt>
          <dd>{item.creator}</dd>
        </div>
      </dl>
    </div>
  )
}
