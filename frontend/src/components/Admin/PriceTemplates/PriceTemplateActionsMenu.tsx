import { EllipsisVertical } from "lucide-react"
import { useState } from "react"

import type { PriceTemplatePublic } from "@/client"
import { Button } from "@/components/ui/button"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import DeletePriceTemplate from "./DeletePriceTemplate"
import EditPriceTemplate from "./EditPriceTemplate"

interface PriceTemplateActionsMenuProps {
  template: PriceTemplatePublic
}

export const PriceTemplateActionsMenu = ({
  template,
}: PriceTemplateActionsMenuProps) => {
  const [open, setOpen] = useState(false)

  return (
    <DropdownMenu open={open} onOpenChange={setOpen}>
      <DropdownMenuTrigger asChild>
        <Button variant="ghost" size="icon">
          <EllipsisVertical />
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end">
        <EditPriceTemplate
          template={template}
          onSuccess={() => setOpen(false)}
        />
        <DeletePriceTemplate
          id={template.id}
          name={template.name}
          onSuccess={() => setOpen(false)}
        />
      </DropdownMenuContent>
    </DropdownMenu>
  )
}
