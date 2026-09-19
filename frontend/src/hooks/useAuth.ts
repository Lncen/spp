import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { useNavigate } from "@tanstack/react-router"

import {
  type Body_login_login_access_token as AccessToken,
  LoginService,
  type UserPublic,
  type UserRegister,
  UsersService,
} from "@/client"
import { handleError } from "@/utils"
import useCustomToast from "./useCustomToast"
import { PERMISSIONS_QUERY_KEY } from "./usePermissions"

const isLoggedIn = () => {
  return localStorage.getItem("access_token") !== null
}

const getCurrentUserQueryOptions = () => ({
  queryKey: ["currentUser"],
  queryFn: UsersService.readUserMe,
  staleTime: 5 * 60 * 1000,
})

const useAuth = () => {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const { showErrorToast } = useCustomToast()

  const { data: user } = useQuery<UserPublic | null, Error>({
    ...getCurrentUserQueryOptions(),
    enabled: isLoggedIn(),
  })

  const signUpMutation = useMutation({
    mutationFn: (data: UserRegister) =>
      UsersService.registerUser({ requestBody: data }),
    onSuccess: () => {
      navigate({ to: "/login" })
    },
    onError: handleError.bind(showErrorToast),
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: ["users"] })
    },
  })

  const login = async (data: AccessToken) => {
    const response = await LoginService.loginAccessToken({
      formData: data,
    })
    localStorage.setItem("access_token", response.access_token)
  }

  const loginMutation = useMutation({
    mutationFn: login,
    onSuccess: () => {
      // 换账号登录时清除上一个账号的权限缓存，避免菜单沿用旧权限
      queryClient.removeQueries({ queryKey: PERMISSIONS_QUERY_KEY })
      navigate({ to: "/" })
    },
    onError: handleError.bind(showErrorToast),
  })

  const logout = () => {
    localStorage.removeItem("access_token")
    queryClient.removeQueries({ queryKey: PERMISSIONS_QUERY_KEY })
    navigate({ to: "/login" })
  }

  return {
    signUpMutation,
    loginMutation,
    logout,
    user,
  }
}

export { getCurrentUserQueryOptions, isLoggedIn }
export default useAuth
