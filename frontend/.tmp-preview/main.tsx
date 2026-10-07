import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { createRoot } from "react-dom/client"

import { Combos } from "@/components/Combos/Combos"
import "./preview.css"

const queryClient = new QueryClient({
  defaultOptions: { queries: { retry: false } },
})

const root = document.getElementById("root")
if (root) {
  createRoot(root).render(
    <QueryClientProvider client={queryClient}>
      {/* 模拟真实布局：左侧 16rem 侧边栏 + main 内边距 */}
      <div className="w-[calc(100vw-256px)] p-6 md:p-8">
        <Combos />
      </div>
    </QueryClientProvider>,
  )
}
