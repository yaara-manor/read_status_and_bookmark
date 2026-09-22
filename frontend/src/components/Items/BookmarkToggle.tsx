import { useMutation, useQueryClient } from "@tanstack/react-query"
import { Bookmark } from "lucide-react"

import { type ItemPublic, type ItemsPublic, ItemsService } from "@/client"
import { Button } from "@/components/ui/button"
import { cn } from "@/lib/utils"

function patchList(
  old: ItemsPublic | undefined,
  itemId: string,
  is_bookmarked: boolean,
) {
  if (!old?.data) {
    return old
  }
  return {
    ...old,
    data: old.data.map((row) =>
      row.id === itemId ? { ...row, is_bookmarked } : row,
    ),
  }
}

export function BookmarkToggle({ item }: { item: ItemPublic }) {
  const queryClient = useQueryClient()
  const mutation = useMutation({
    mutationFn: (is_bookmarked: boolean) =>
      ItemsService.setItemBookmark({
        path: { id: item.id },
        body: { is_bookmarked },
      }),
    onMutate: async (is_bookmarked) => {
      const previousItems = queryClient.getQueryData<ItemsPublic>(["items"])
      const previousItem = queryClient.getQueryData<ItemPublic>([
        "items",
        item.id,
      ])
      const previousBookmarked = queryClient.getQueryData<ItemsPublic>([
        "bookmarked",
      ])
      if (previousItems?.data) {
        queryClient.setQueryData(
          ["items"],
          patchList(previousItems, item.id, is_bookmarked),
        )
      }
      if (previousItem) {
        queryClient.setQueryData(["items", item.id], {
          ...previousItem,
          is_bookmarked,
        })
      }
      if (previousBookmarked?.data) {
        if (!is_bookmarked) {
          const data = previousBookmarked.data.filter(
            (row) => row.id !== item.id,
          )
          queryClient.setQueryData(["bookmarked"], {
            ...previousBookmarked,
            data,
            count: data.length,
          })
        } else {
          queryClient.setQueryData(
            ["bookmarked"],
            patchList(previousBookmarked, item.id, true),
          )
        }
      }
      return { previousItems, previousItem, previousBookmarked }
    },
    onError: (_err, _vars, ctx) => {
      if (ctx?.previousItems) {
        queryClient.setQueryData(["items"], ctx.previousItems)
      }
      if (ctx?.previousItem) {
        queryClient.setQueryData(["items", item.id], ctx.previousItem)
      }
      if (ctx?.previousBookmarked) {
        queryClient.setQueryData(["bookmarked"], ctx.previousBookmarked)
      }
    },
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: ["items"] })
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
      aria-label={item.is_bookmarked ? "Remove bookmark" : "Bookmark"}
      aria-pressed={Boolean(item.is_bookmarked)}
      onClick={(e) => {
        e.stopPropagation()
        mutation.mutate(!item.is_bookmarked)
      }}
    >
      <Bookmark
        className={cn("size-4", item.is_bookmarked && "fill-current")}
      />
    </Button>
  )
}
