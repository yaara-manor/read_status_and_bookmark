import { EllipsisVertical } from "lucide-react"
import { useState } from "react"

import type { EventPublic } from "@/client"
import { Button } from "@/components/ui/button"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import useAuth from "@/hooks/useAuth"
import DeleteEvent from "./DeleteEvent"
import EditEvent from "./EditEvent"

interface EventActionsMenuProps {
  event: EventPublic
  onDeleted?: () => void
}

export const EventActionsMenu = ({
  event,
  onDeleted,
}: EventActionsMenuProps) => {
  const { user } = useAuth()
  const [open, setOpen] = useState(false)

  if (!user || (event.owner_id !== user.id && !user.is_superuser)) {
    return null
  }

  return (
    <DropdownMenu open={open} onOpenChange={setOpen}>
      <DropdownMenuTrigger asChild>
        <Button
          variant="ghost"
          size="icon"
          aria-label="Event actions"
          onClick={(e) => e.stopPropagation()}
        >
          <EllipsisVertical />
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end">
        <EditEvent event={event} onSuccess={() => setOpen(false)} />
        <DeleteEvent
          id={event.id}
          onSuccess={() => {
            setOpen(false)
            onDeleted?.()
          }}
        />
      </DropdownMenuContent>
    </DropdownMenu>
  )
}
