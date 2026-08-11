import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { useState } from "react"

import { type UserPublic, type WalletPublic, WalletsService } from "@/client"
import { Badge } from "@/components/ui/badge"
import { Input } from "@/components/ui/input"
import { LoadingButton } from "@/components/ui/loading-button"
import { Skeleton } from "@/components/ui/skeleton"
import { Switch } from "@/components/ui/switch"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import useCustomToast from "@/hooks/useCustomToast"
import { cn } from "@/lib/utils"
import { handleError } from "@/utils"
import { formatBalance, formatDateTime } from "./format"

const TX_TYPE_LABELS: Record<string, string> = {
  recharge: "充值",
  consume: "消费",
  refund: "退款",
  adjust: "调账",
}

interface WalletPanelProps {
  user: UserPublic
  wallet?: WalletPublic
  isWalletLoading: boolean
}

export function WalletPanel({
  user,
  wallet,
  isWalletLoading,
}: WalletPanelProps) {
  const [walletTab, setWalletTab] = useState<"balance" | "transactions">(
    "balance",
  )
  const [adjustAmount, setAdjustAmount] = useState("")
  const [adjustRemark, setAdjustRemark] = useState("")
  const queryClient = useQueryClient()
  const { showSuccessToast, showErrorToast } = useCustomToast()

  const { data: transactions, isLoading: isTransactionsLoading } = useQuery({
    queryKey: ["wallet-transactions", user.id, wallet?.id],
    queryFn: () =>
      WalletsService.readWalletTransactions({
        walletId: wallet!.id,
        limit: 50,
      }),
    enabled: Boolean(wallet?.id) && walletTab === "transactions",
  })

  const statusMutation = useMutation({
    mutationFn: (data: { walletId: string; isActive: boolean }) =>
      WalletsService.updateWalletStatus({
        walletId: data.walletId,
        requestBody: { is_active: data.isActive },
      }),
    onSuccess: () => {
      showSuccessToast("钱包状态已更新")
      queryClient.invalidateQueries({ queryKey: ["wallet", user.id] })
    },
    onError: handleError.bind(showErrorToast),
  })

  const adjustMutation = useMutation({
    mutationFn: (data: { walletId: string; amount: string; remark: string }) =>
      WalletsService.adjustWalletBalance({
        walletId: data.walletId,
        requestBody: { amount: data.amount, remark: data.remark },
      }),
    onSuccess: () => {
      showSuccessToast("余额调整成功")
      setAdjustAmount("")
      setAdjustRemark("")
      queryClient.invalidateQueries({ queryKey: ["wallet", user.id] })
    },
    onError: handleError.bind(showErrorToast),
  })

  const handleAdjustBalance = () => {
    if (!wallet || !adjustAmount || !adjustRemark) return
    adjustMutation.mutate({
      walletId: wallet.id,
      amount: adjustAmount,
      remark: adjustRemark,
    })
  }

  return (
    <Tabs
      value={walletTab}
      onValueChange={(value) =>
        setWalletTab(value as "balance" | "transactions")
      }
      className="flex flex-col gap-4"
    >
      <TabsList className="flex h-auto w-fit items-center gap-6 rounded-none border-b border-border bg-transparent p-0">
        <TabsTrigger
          value="balance"
          className="flex-none rounded-none border-0 bg-transparent px-1 py-2 text-muted-foreground shadow-none data-[state=active]:border-b-2 data-[state=active]:border-primary data-[state=active]:bg-transparent data-[state=active]:text-foreground data-[state=active]:shadow-none"
        >
          余额
        </TabsTrigger>
        <TabsTrigger
          value="transactions"
          className="flex-none rounded-none border-0 bg-transparent px-1 py-2 text-muted-foreground shadow-none data-[state=active]:border-b-2 data-[state=active]:border-primary data-[state=active]:bg-transparent data-[state=active]:text-foreground data-[state=active]:shadow-none"
        >
          流水
        </TabsTrigger>
      </TabsList>

      <TabsContent value="balance">
        <div className="flex flex-col gap-4">
          <div className="flex items-center justify-between rounded-lg border p-4">
            <div className="flex flex-col gap-1">
              <span className="text-muted-foreground text-sm">当前余额</span>
              {isWalletLoading ? (
                <Skeleton className="h-8 w-32" />
              ) : (
                <span className="text-2xl font-semibold">
                  ¥ {formatBalance(wallet?.balance)}
                </span>
              )}
            </div>

            <Badge
              variant={
                wallet?.is_active === false ? "destructive" : "secondary"
              }
            >
              {wallet?.is_active === false ? "禁用" : "启用"}
              <Switch
                checked={wallet?.is_active ?? true}
                disabled={!wallet || statusMutation.isPending}
                onCheckedChange={(value) => {
                  if (!wallet) return
                  statusMutation.mutate({
                    walletId: wallet.id,
                    isActive: value,
                  })
                }}
              />
            </Badge>
          </div>

          <div className="flex flex-col gap-4 border-t pt-4">
            <span className="text-sm font-medium">调整余额</span>
            <div className="flex items-start gap-3">
              <span className="w-24 shrink-0 pt-2 text-right text-sm font-medium">
                金额
              </span>
              <div className="flex min-w-0 flex-1 flex-col gap-1.5">
                <Input
                  type="number"
                  step="0.01"
                  placeholder="正数入账，负数扣款"
                  value={adjustAmount}
                  onChange={(e) => setAdjustAmount(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter") e.preventDefault()
                  }}
                />
              </div>
            </div>
            <div className="flex items-start gap-3">
              <span className="w-24 shrink-0 pt-2 text-right text-sm font-medium">
                备注
              </span>
              <div className="flex min-w-0 flex-1 flex-col gap-1.5">
                <Input
                  placeholder="调整备注（必填）"
                  value={adjustRemark}
                  onChange={(e) => setAdjustRemark(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter") e.preventDefault()
                  }}
                />
              </div>
            </div>
            <div className="flex justify-end">
              <LoadingButton
                type="button"
                variant="outline"
                loading={adjustMutation.isPending}
                disabled={!wallet || !adjustAmount || !adjustRemark}
                onClick={handleAdjustBalance}
              >
                调整余额
              </LoadingButton>
            </div>
          </div>
        </div>
      </TabsContent>

      <TabsContent value="transactions">
        <div className="flex flex-col gap-2">
          {isTransactionsLoading ? (
            <Skeleton className="h-24 w-full" />
          ) : transactions?.data.length ? (
            transactions.data.map((tx) => (
              <div
                key={tx.id}
                className="flex items-center justify-between gap-4 rounded-lg border px-3 py-2"
              >
                <div className="flex min-w-0 flex-col gap-0.5">
                  <span className="text-sm font-medium">
                    {TX_TYPE_LABELS[tx.tx_type] ?? tx.tx_type}
                  </span>
                  {tx.remark && (
                    <span className="text-muted-foreground truncate text-xs">
                      {tx.remark}
                    </span>
                  )}
                  <span className="text-muted-foreground text-xs">
                    {formatDateTime(tx.created_at)}
                  </span>
                </div>
                <div className="flex shrink-0 flex-col items-end gap-0.5">
                  <span
                    className={cn(
                      "text-sm font-semibold",
                      Number(tx.amount) < 0 && "text-destructive",
                    )}
                  >
                    {Number(tx.amount) > 0 ? "+" : ""}
                    {formatBalance(tx.amount)}
                  </span>
                  <span className="text-muted-foreground text-xs">
                    余额 {formatBalance(tx.balance_after)}
                  </span>
                </div>
              </div>
            ))
          ) : (
            <div className="text-muted-foreground rounded-lg border p-4 text-center text-sm">
              暂无流水
            </div>
          )}
        </div>
      </TabsContent>
    </Tabs>
  )
}
