import { EllipsisVertical } from "lucide-react"
import { useState } from "react"

import type { ItemPublic } from "@/client"
import { Button } from "@/components/ui/button"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import useAuth from "@/hooks/useAuth"
import DeleteItem from "../Items/DeleteItem"
import EditItem from "../Items/EditItem"

interface ItemActionsMenuProps {
  item: ItemPublic
  onDeleted?: () => void
}

export const ItemActionsMenu = ({ item, onDeleted }: ItemActionsMenuProps) => {
  const { user } = useAuth()
  const [open, setOpen] = useState(false)

  if (!user || (item.owner_id !== user.id && !user.is_superuser)) {
    return null
  }

  return (
    <DropdownMenu open={open} onOpenChange={setOpen}>
      <DropdownMenuTrigger asChild>
        <Button variant="ghost" size="icon" aria-label="Item actions">
          <EllipsisVertical />
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end">
        <EditItem item={item} onSuccess={() => setOpen(false)} />
        <DeleteItem
          id={item.id}
          onSuccess={() => {
            setOpen(false)
            onDeleted?.()
          }}
        />
      </DropdownMenuContent>
    </DropdownMenu>
  )
}
