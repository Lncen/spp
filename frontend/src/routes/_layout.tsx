import { createFileRoute, Outlet, redirect } from "@tanstack/react-router"
import { ChatDialog } from "@/components/Chat/ChatDialog"
import { ChatProvider } from "@/components/Chat/ChatProvider"
import { RealtimeChatBridge } from "@/components/Chat/RealtimeChatBridge"
import { Footer } from "@/components/Common/Footer"
import {
  BreadcrumbLabelProvider,
  PageBreadcrumb,
} from "@/components/Common/PageBreadcrumb"
import { NotificationsDialog } from "@/components/Notifications/NotificationsDialog"
import { NotificationsProvider } from "@/components/Notifications/NotificationsProvider"
import { RealtimeNotificationBridge } from "@/components/Notifications/RealtimeNotificationBridge"
import AppSidebar from "@/components/Sidebar/AppSidebar"
import { Separator } from "@/components/ui/separator"
import {
  SidebarInset,
  SidebarProvider,
  SidebarTrigger,
} from "@/components/ui/sidebar"
import { isLoggedIn } from "@/hooks/useAuth"
import { RealtimeProvider } from "@/realtime/RealtimeProvider"

export const Route = createFileRoute("/_layout")({
  component: Layout,
  beforeLoad: async () => {
    if (!isLoggedIn()) {
      throw redirect({
        to: "/login",
      })
    }
  },
})

function Layout() {
  return (
    <RealtimeProvider>
      <NotificationsProvider>
        <ChatProvider>
          <SidebarProvider>
            <AppSidebar />
            <SidebarInset>
              <BreadcrumbLabelProvider>
                <header className="sticky top-0 z-10 flex h-16 shrink-0 items-center gap-2 border-b px-4">
                  <SidebarTrigger className="-ml-1 text-muted-foreground" />
                  <Separator
                    orientation="vertical"
                    className="mr-2 data-[orientation=vertical]:h-4"
                  />
                  <PageBreadcrumb />
                </header>
                <main className="flex-1 p-6 md:p-8">
                  <div className="mx-auto ">
                    <Outlet />
                  </div>
                </main>
              </BreadcrumbLabelProvider>
              <Footer />
            </SidebarInset>
            <RealtimeNotificationBridge />
            <RealtimeChatBridge />
          </SidebarProvider>
          <NotificationsDialog />
          <ChatDialog />
        </ChatProvider>
      </NotificationsProvider>
    </RealtimeProvider>
  )
}
