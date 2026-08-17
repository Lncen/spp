import { z } from "zod"

export const formSchema = z
  .object({
    email: z
      .email({ message: "邮箱格式不正确" })
      .optional()
      .or(z.literal("")),
    username: z
      .string()
      .min(1, { message: "请输入用户名" })
      .min(6, { message: "用户名至少 6 个字符" })
      .max(20, { message: "用户名最多 20 个字符" }),
    full_name: z.string().optional(),
    password: z
      .string()
      .min(8, { message: "密码至少 8 个字符" })
      .optional()
      .or(z.literal("")),
    confirm_password: z.string().optional(),
    is_superuser: z.boolean().optional(),
    is_active: z.boolean().optional(),
    can_order: z.boolean().optional(),
    level_id: z.string().optional(),
    avatar_id: z.string().optional(),
    remark: z.string().max(255, "备注不能超过 255 个字符").optional(),
    bio: z.string().max(1000, "简介不能超过 1000 个字符").optional(),
  })
  .refine((data) => !data.password || data.password === data.confirm_password, {
    message: "两次输入的密码不一致",
    path: ["confirm_password"],
  })

export type FormData = z.infer<typeof formSchema>
