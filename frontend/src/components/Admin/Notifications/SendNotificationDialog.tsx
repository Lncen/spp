import { Send } from "lucide-react"
import { useState } from "react"

import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog"
import { SendNotificationForm } from "./SendNotificationForm"

export const SendNotificationDialog = () => {
  const [isOpen, setIsOpen] = useState(false)

  return (
    <Dialog open={isOpen} onOpenChange={setIsOpen}>
      <DialogTrigger asChild>
        <Button>
          <Send className="mr-2" />
          群发通知
        </Button>
      </DialogTrigger>
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>群发通知</DialogTitle>
          <DialogDescription>
            向全部启用用户发送通知并异步投递，可同时选择站内与邮件渠道
          </DialogDescription>
        </DialogHeader>
        <SendNotificationForm broadcast onSuccess={() => setIsOpen(false)} />
      </DialogContent>
    </Dialog>
  )
}

export default SendNotificationDialog
