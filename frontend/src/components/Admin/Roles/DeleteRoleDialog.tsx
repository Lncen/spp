import { useMutation, useQueryClient } from "@tanstack/react-query"
import { Trash2 } from "lucide-react"
import { useState } from "react"

import { type RolePublic, RolesService } from "@/client"
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
import { LoadingButton } from "@/components/ui/loading-button"
import useCustomToast from "@/hooks/useCustomToast"
import { handleError } from "@/utils"
import { ROLES_QUERY_KEY } from "./constants"

interface DeleteRoleDialogProps {
  role: RolePublic
  /** 删除成功后回调，用于切换当前选中角色 */
  onDeleted: (roleId: string) => void
}

export function DeleteRoleDialog({ role, onDeleted }: DeleteRoleDialogProps) {
  const [isOpen, setIsOpen] = useState(false)
  const queryClient = useQueryClient()
  const { showSuccessToast, showErrorToast } = useCustomToast()

  const mutation = useMutation({
    mutationFn: () => RolesService.deleteRoleEndpoint({ roleId: role.id }),
    onSuccess: () => {
      showSuccessToast(`角色「${role.name}」已删除`)
      setIsOpen(false)
      onDeleted(role.id)
    },
    onError: handleError.bind(showErrorToast),
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: ROLES_QUERY_KEY })
    },
  })

  return (
    <Dialog open={isOpen} onOpenChange={setIsOpen}>
      <Button
        variant="outline"
        size="sm"
        disabled={role.is_system}
        title={role.is_system ? "系统内置角色不可删除" : undefined}
        onClick={() => setIsOpen(true)}
      >
        <Trash2 data-icon="inline-start" />
        删除
      </Button>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>删除角色</DialogTitle>
          <DialogDescription>
            确定要删除角色 <strong>{role.name}</strong> 吗？
            该角色下的用户分配会一并解除，此操作不可撤销。
          </DialogDescription>
        </DialogHeader>
        <DialogFooter className="mt-4">
          <DialogClose asChild>
            <Button variant="outline" disabled={mutation.isPending}>
              取消
            </Button>
          </DialogClose>
          <LoadingButton
            variant="destructive"
            type="button"
            loading={mutation.isPending}
            onClick={() => mutation.mutate()}
          >
            删除
          </LoadingButton>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
