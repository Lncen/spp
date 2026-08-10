import { useMutation, useQueryClient } from "@tanstack/react-query"
import { Play, Square } from "lucide-react"
import { useState } from "react"

import type { AutomationRulePublic } from "@/client"
import { AutomationService } from "@/client"
import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { DropdownMenuItem } from "@/components/ui/dropdown-menu"
import { LoadingButton } from "@/components/ui/loading-button"
import useCustomToast from "@/hooks/useCustomToast"
import { handleError } from "@/utils"

interface ToggleRuleDialogProps {
  rule: AutomationRulePublic
  onSuccess: () => void
}

export const ToggleRuleDialog = ({
  rule,
  onSuccess,
}: ToggleRuleDialogProps) => {
  const [isOpen, setIsOpen] = useState(false)
  const queryClient = useQueryClient()
  const { showSuccessToast, showErrorToast } = useCustomToast()

  const mutation = useMutation({
    mutationFn: () => AutomationService.toggleAutomationRule({ id: rule.id }),
    onSuccess: (data) => {
      showSuccessToast(`规则已${data.is_active ? "启用" : "停用"}`)
      setIsOpen(false)
      onSuccess()
    },
    onError: handleError.bind(showErrorToast),
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: ["automation-rules"] })
    },
  })

  return (
    <Dialog open={isOpen} onOpenChange={setIsOpen}>
      <DropdownMenuItem
        onSelect={(e) => e.preventDefault()}
        onClick={() => setIsOpen(true)}
      >
        {rule.is_active ? <Square /> : <Play />}
        {rule.is_active ? "停用" : "启用"}
      </DropdownMenuItem>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>{rule.is_active ? "停用规则" : "启用规则"}</DialogTitle>
          <DialogDescription>
            确定要{rule.is_active ? "停用" : "启用"}规则{" "}
            <strong>
              {rule.event_type} → {rule.action_type}
            </strong>{" "}
            吗？
          </DialogDescription>
        </DialogHeader>
        <DialogFooter className="mt-4">
          <DialogClose asChild>
            <Button variant="outline" disabled={mutation.isPending}>
              取消
            </Button>
          </DialogClose>
          <LoadingButton
            type="button"
            loading={mutation.isPending}
            onClick={() => mutation.mutate()}
          >
            确认
          </LoadingButton>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

export default ToggleRuleDialog
