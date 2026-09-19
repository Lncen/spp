import {
  createContext,
  type ReactNode,
  useContext,
  useEffect,
  useState,
} from "react"
import { io, type Socket } from "socket.io-client"

const SOCKET_PATH = "/socket.io"

declare global {
  interface Window {
    /** 仅开发环境：便于在控制台排查实时通道（例如 __realtimeSocket.connected） */
    __realtimeSocket?: Socket
  }
}

type RealtimeContextValue = {
  socket: Socket | null
  isConnected: boolean
}

const RealtimeContext = createContext<RealtimeContextValue>({
  socket: null,
  isConnected: false,
})

export function RealtimeProvider({ children }: { children: ReactNode }) {
  const [socket, setSocket] = useState<Socket | null>(null)
  const [isConnected, setIsConnected] = useState(false)

  useEffect(() => {
    const token = localStorage.getItem("access_token")
    if (!token) return

    const apiUrl = new URL(import.meta.env.VITE_API_URL as string)
    const client = io(apiUrl.origin, {
      path: SOCKET_PATH,
      // polling 优先：握手阶段更稳，避免部分网络环境 WebSocket 升级失败导致
      // 实时通道不可用；连接建立后 socket.io 会自动升级到 WebSocket
      transports: ["polling", "websocket"],
      // 每次（重）连都取当前 token：token 轮换、后端重启后的重连也能带上最新凭证
      auth: (callback) => {
        callback({ token: localStorage.getItem("access_token") ?? "" })
      },
    })
    setSocket(client)

    client.on("connect", () => setIsConnected(true))
    client.on("disconnect", () => setIsConnected(false))
    client.on("connect_error", (error) => {
      setIsConnected(false)
      console.warn("[realtime] connect_error:", error.message)
      // 已登出（本地无 token）才停止重试；token 仍存在时保留自动重连，
      // 否则一次握手失败会让实时提醒永久失效，直到刷新页面
      if (
        error.message === "unauthorized" &&
        !localStorage.getItem("access_token")
      ) {
        client.disconnect()
      }
    })

    if (import.meta.env.DEV) {
      window.__realtimeSocket = client
    }

    // 回到前台时若连接已断，主动补一次重连（后台标签页会节流定时器）
    const handleVisibilityChange = () => {
      if (document.visibilityState === "visible" && !client.connected) {
        client.connect()
      }
    }
    document.addEventListener("visibilitychange", handleVisibilityChange)

    return () => {
      document.removeEventListener("visibilitychange", handleVisibilityChange)
      client.disconnect()
      if (import.meta.env.DEV && window.__realtimeSocket === client) {
        window.__realtimeSocket = undefined
      }
      setSocket(null)
      setIsConnected(false)
    }
  }, [])

  return (
    <RealtimeContext.Provider value={{ socket, isConnected }}>
      {children}
    </RealtimeContext.Provider>
  )
}

export function useRealtime() {
  return useContext(RealtimeContext)
}
