import { createFileRoute, Outlet, redirect } from "@tanstack/react-router"

import { Footer } from "@/components/Common/Footer"
import { PageBreadcrumb } from "@/components/Common/PageBreadcrumb"
import { CustomerServiceDialog } from "@/components/CustomerService/CustomerServiceDialog"
import { CustomerServiceProvider } from "@/components/CustomerService/CustomerServiceProvider"
import { RealtimeCustomerServiceBridge } from "@/components/CustomerService/RealtimeCustomerServiceBridge"
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
      <CustomerServiceProvider>
        <SidebarProvider>
          <AppSidebar />
          <SidebarInset>
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
            <Footer />
          </SidebarInset>
          <RealtimeCustomerServiceBridge />
          <RealtimeNotificationBridge />
        </SidebarProvider>
        <CustomerServiceDialog />
      </CustomerServiceProvider>
    </RealtimeProvider>
  )
}
