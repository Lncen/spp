import { useFormContext } from "react-hook-form"

import type { LevelsPublic } from "@/client"
import { FormControl, FormField, FormMessage } from "@/components/ui/form"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { Skeleton } from "@/components/ui/skeleton"
import type { FormData } from "./editUserForm"
import { HorizontalFormItem } from "./formParts"

interface LevelFieldsProps {
  levels?: LevelsPublic
  isLevelsLoading: boolean
}

export function LevelFields({ levels, isLevelsLoading }: LevelFieldsProps) {
  const { control, watch } = useFormContext<FormData>()
  const levelId = watch("level_id")
  const currentLevel = levels?.data.find((level) => level.id === levelId)

  return (
    <div className="flex flex-col gap-4">
      <FormField
        control={control}
        name="level_id"
        render={({ field }) => (
          <HorizontalFormItem label="用户等级">
            {isLevelsLoading ? (
              <Skeleton className="h-9 w-full" />
            ) : (
              <Select value={field.value ?? ""} onValueChange={field.onChange}>
                <FormControl>
                  <SelectTrigger className="w-full">
                    <SelectValue
                      placeholder={
                        currentLevel
                          ? `Lv.${currentLevel.level} - ${currentLevel.name}`
                          : "请选择等级"
                      }
                    />
                  </SelectTrigger>
                </FormControl>
                <SelectContent>
                  {levels?.data.map((level) => (
                    <SelectItem key={level.id} value={level.id}>
                      Lv.{level.level} - {level.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            )}
            <FormMessage />
          </HorizontalFormItem>
        )}
      />
    </div>
  )
}
