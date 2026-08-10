import { EllipsisVertical } from "lucide-react"
import { useState } from "react"

import type { AutomationRulePublic } from "@/client"
import { Button } from "@/components/ui/button"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import DeleteRuleDialog from "./DeleteRuleDialog"
import RuleFormDialog from "./RuleFormDialog"
import ToggleRuleDialog from "./ToggleRuleDialog"

interface RuleActionsMenuProps {
  rule: AutomationRulePublic
}

export const RuleActionsMenu = ({ rule }: RuleActionsMenuProps) => {
  const [open, setOpen] = useState(false)

  return (
    <DropdownMenu open={open} onOpenChange={setOpen}>
      <DropdownMenuTrigger asChild>
        <Button variant="ghost" size="icon">
          <EllipsisVertical />
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end">
        <RuleFormDialog rule={rule} onSuccess={() => setOpen(false)} />
        <ToggleRuleDialog rule={rule} onSuccess={() => setOpen(false)} />
        <DeleteRuleDialog rule={rule} onSuccess={() => setOpen(false)} />
      </DropdownMenuContent>
    </DropdownMenu>
  )
}

export default RuleActionsMenu
