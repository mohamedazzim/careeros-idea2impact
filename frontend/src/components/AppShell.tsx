"use client";

import { usePathname } from "next/navigation";
import Navigation from "@/components/Navigation";
import { isPublicRoute } from "@/lib/rbac";
import SessionMonitor from "@/components/SessionMonitor";

export default function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();

  if (isPublicRoute(pathname)) {
    return <main id="main-content">{children}</main>;
  }

  return (
    <>
      <SessionMonitor />
      <Navigation />
      <main id="main-content" className="lg:ml-56">
        {children}
      </main>
    </>
  );
}
