import { ChevronRight, Search } from "lucide-react"
import { useMemo, useState } from "react"
import { useFormContext } from "react-hook-form"

import type { PermissionTreeCategory } from "@/client"
import { Badge } from "@/components/ui/badge"
import { Checkbox } from "@/components/ui/checkbox"
import {
  FormControl,
  FormField,
  FormItem,
  FormLabel,
} from "@/components/ui/form"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group"
import { Separator } from "@/components/ui/separator"
import { Skeleton } from "@/components/ui/skeleton"
import { cn } from "@/lib/utils"
import type { FormData } from "./editUserForm"

/** 用户直授权限草稿：允许与拒绝两组权限码，同一权限只会出现在其中一组 */
export interface UserPermissionDraft {
  allowCodes: string[]
  denyCodes: string[]
}

/** 单个权限的直授状态，``unset`` 表示不设置、完全跟随角色 */
type PermissionState = "allow" | "deny" | "unset"

const STATE_OPTIONS: { value: PermissionState; label: string }[] = [
  { value: "allow", label: "允许" },
  { value: "deny", label: "拒绝" },
  { value: "unset", label: "不设置" },
]

interface PermissionsFieldsProps {
  /** 权限树（分类 + 权限） */
  tree?: PermissionTreeCategory[]
  isTreeLoading: boolean
  /** 已分配角色带来的权限码，仅用于只读提示 */
  roleCodes: Set<string>
  draft: UserPermissionDraft
  onChange: (next: UserPermissionDraft) => void
}

export function PermissionsFields({
  tree,
  isTreeLoading,
  roleCodes,
  draft,
  onChange,
}: PermissionsFieldsProps) {
  const { control, watch } = useFormContext<FormData>()
  const isSuperuser = watch("is_superuser")
  const [keyword, setKeyword] = useState("")
  const [collapsedIds, setCollapsedIds] = useState<string[]>([])

  const allowSet = useMemo(() => new Set(draft.allowCodes), [draft.allowCodes])
  const denySet = useMemo(() => new Set(draft.denyCodes), [draft.denyCodes])

  /** 三态切换：允许与拒绝互斥，选「不设置」即从两组中移除 */
  const setPermissionState = (code: string, next: PermissionState) => {
    const allow = new Set(draft.allowCodes)
    const deny = new Set(draft.denyCodes)
    allow.delete(code)
    deny.delete(code)
    if (next === "allow") {
      allow.add(code)
    }
    if (next === "deny") {
      deny.add(code)
    }
    onChange({ allowCodes: [...allow], denyCodes: [...deny] })
  }

  const toggleCategory = (categoryId: string) => {
    setCollapsedIds((current) =>
      current.includes(categoryId)
        ? current.filter((id) => id !== categoryId)
        : [...current, categoryId],
    )
  }

  const normalizedKeyword = keyword.trim().toLowerCase()
  const visibleCategories = (tree ?? [])
    .map((category) => ({
      category,
      permissions: normalizedKeyword
        ? category.permissions.filter((permission) =>
            [permission.name, permission.code, permission.description]
              .filter(Boolean)
              .some((text) => text?.toLowerCase().includes(normalizedKeyword)),
          )
        : category.permissions,
    }))
    .filter((item) => item.permissions.length > 0)

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-col gap-3">
        <FormField
          control={control}
          name="is_superuser"
          render={({ field }) => (
            <FormItem className="flex items-center gap-3">
              <FormLabel className="w-24 shrink-0 text-right font-normal">
                超级管理员
              </FormLabel>
              <FormControl>
                <Checkbox
                  checked={field.value}
                  onCheckedChange={field.onChange}
                />
              </FormControl>
            </FormItem>
          )}
        />

        <FormField
          control={control}
          name="is_active"
          render={({ field }) => (
            <FormItem className="flex items-center gap-3">
              <FormLabel className="w-24 shrink-0 text-right font-normal">
                启用账号
              </FormLabel>
              <FormControl>
                <Checkbox
                  checked={field.value}
                  onCheckedChange={field.onChange}
                />
              </FormControl>
            </FormItem>
          )}
        />

        <FormField
          control={control}
          name="can_order"
          render={({ field }) => (
            <FormItem className="flex items-center gap-3">
              <FormLabel className="w-24 shrink-0 text-right font-normal">
                允许下单
              </FormLabel>
              <FormControl>
                <Checkbox
                  checked={field.value ?? false}
                  onCheckedChange={field.onChange}
                />
              </FormControl>
            </FormItem>
          )}
        />
      </div>

      <Separator />

      <div className="flex flex-col gap-3">
        <div className="flex flex-col gap-1">
          <span className="text-sm font-medium">直授权限</span>
          <p className="text-xs text-muted-foreground">
            允许：直接授予该权限；拒绝：即使角色带来该权限也会被扣除；不设置：完全跟随角色。修改后与用户信息一起保存。
          </p>
          {isSuperuser ? (
            <p className="text-xs text-amber-600 dark:text-amber-500">
              该账号是超级管理员，拥有全部权限，直授权限与拒绝对它不生效。
            </p>
          ) : null}
        </div>

        <div className="relative">
          <Search className="absolute top-1/2 left-3 size-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            value={keyword}
            onChange={(event) => setKeyword(event.target.value)}
            placeholder="搜索权限"
            className="pl-9"
            aria-label="搜索权限"
          />
        </div>

        {isTreeLoading ? (
          <div className="flex flex-col gap-3">
            {Array.from({ length: 3 }).map((_, index) => (
              <Skeleton key={index} className="h-20 w-full" />
            ))}
          </div>
        ) : visibleCategories.length === 0 ? (
          <p className="py-4 text-sm text-muted-foreground">没有匹配的权限</p>
        ) : (
          visibleCategories.map(({ category, permissions }) => (
            <PermissionCategorySection
              key={category.id}
              category={category}
              permissions={permissions}
              allowSet={allowSet}
              denySet={denySet}
              roleCodes={roleCodes}
              collapsed={collapsedIds.includes(category.id)}
              isSearching={Boolean(normalizedKeyword)}
              onToggleCategory={toggleCategory}
              onTogglePermission={setPermissionState}
            />
          ))
        )}
      </div>
    </div>
  )
}

interface PermissionCategorySectionProps {
  category: PermissionTreeCategory
  permissions: PermissionTreeCategory["permissions"]
  allowSet: Set<string>
  denySet: Set<string>
  roleCodes: Set<string>
  collapsed: boolean
  isSearching: boolean
  onToggleCategory: (categoryId: string) => void
  onTogglePermission: (code: string, next: PermissionState) => void
}

function PermissionCategorySection({
  category,
  permissions,
  allowSet,
  denySet,
  roleCodes,
  collapsed,
  isSearching,
  onToggleCategory,
  onTogglePermission,
}: PermissionCategorySectionProps) {
  const allowCount = category.permissions.filter((permission) =>
    allowSet.has(permission.code),
  ).length
  const denyCount = category.permissions.filter((permission) =>
    denySet.has(permission.code),
  ).length
  const isExpanded = isSearching || !collapsed

  return (
    <section className="flex flex-col gap-3 rounded-lg border p-4">
      <button
        type="button"
        className="flex items-center gap-2"
        onClick={() => onToggleCategory(category.id)}
      >
        <ChevronRight
          className={cn(
            "size-4 text-muted-foreground transition-transform",
            isExpanded && "rotate-90",
          )}
        />
        <span className="text-sm font-medium">{category.name}</span>
        <span className="ml-auto flex items-center gap-2 text-xs tabular-nums text-muted-foreground">
          {denyCount > 0 ? (
            <span className="text-destructive">拒绝 {denyCount}</span>
          ) : null}
          <span>
            允许 {allowCount} / {category.permissions.length}
          </span>
        </span>
      </button>
      {isExpanded ? (
        <div className="flex flex-col gap-2">
          {permissions.map((permission) => {
            const state: PermissionState = allowSet.has(permission.code)
              ? "allow"
              : denySet.has(permission.code)
                ? "deny"
                : "unset"

            return (
              <div
                key={permission.id}
                className="flex flex-wrap items-center gap-x-3 gap-y-1"
              >
                <span
                  className="min-w-0 flex-1 truncate text-sm"
                  title={`${permission.name}（${permission.code}）`}
                >
                  {permission.name}
                </span>
                {roleCodes.has(permission.code) ? (
                  <Badge variant="secondary" className="shrink-0">
                    来自角色
                  </Badge>
                ) : null}
                <RadioGroup
                  className="flex shrink-0 items-center gap-3"
                  value={state}
                  onValueChange={(value) =>
                    onTogglePermission(
                      permission.code,
                      value as PermissionState,
                    )
                  }
                >
                  {STATE_OPTIONS.map((option) => (
                    <div key={option.value} className="flex items-center gap-1">
                      <RadioGroupItem
                        value={option.value}
                        id={`${permission.id}-${option.value}`}
                      />
                      <Label
                        htmlFor={`${permission.id}-${option.value}`}
                        className="text-xs font-normal"
                      >
                        {option.label}
                      </Label>
                    </div>
                  ))}
                </RadioGroup>
              </div>
            )
          })}
        </div>
      ) : null}
    </section>
  )
}
