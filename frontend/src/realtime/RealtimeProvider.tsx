import {
  createContext,
  type ReactNode,
  useContext,
  useEffect,
  useState,
} from "react"
import { io, type Socket } from "socket.io-client"

const SOCKET_PATH = "/socket.io"

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
      transports: ["websocket"],
      auth: { token },
    })
    setSocket(client)

    client.on("connect", () => setIsConnected(true))
    client.on("disconnect", () => setIsConnected(false))
    client.on("connect_error", (error) => {
      // token 无效时停止重试，避免无效连接持续占用资源
      if (error.message === "unauthorized") {
        client.disconnect()
      }
    })

    return () => {
      client.disconnect()
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
