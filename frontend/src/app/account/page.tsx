"use client";

import { useRouter } from "next/navigation";
import { LogOut, Mail, ShieldCheck, UserRound } from "lucide-react";
import { useCareerOS } from "@/hooks/useCareerOS";

export default function AccountPage() {
  const { currentUser, userRole, logout } = useCareerOS();
  const router = useRouter();

  const handleLogout = async () => {
    await logout();
    router.replace("/login");
    router.refresh();
  };

  return (
    <div className="min-h-screen bg-slate-50 p-4 text-slate-900 sm:p-6">
      <div className="mx-auto max-w-3xl space-y-6">
        <header>
          <p className="text-xs font-semibold uppercase tracking-wider text-indigo-600">Workspace identity</p>
          <h1 className="mt-1 text-2xl font-bold">Account</h1>
          <p className="mt-2 text-sm text-slate-500">Review the identity and access level used by this CareerOS session.</p>
        </header>

        <section className="rounded-lg border border-slate-200 bg-white p-6 shadow-sm">
          {currentUser ? (
            <dl className="grid gap-5 sm:grid-cols-2">
              <div>
                <dt className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-slate-400">
                  <Mail className="h-4 w-4" /> Email
                </dt>
                <dd className="mt-2 text-sm font-medium">{currentUser.email}</dd>
              </div>
              <div>
                <dt className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-slate-400">
                  <ShieldCheck className="h-4 w-4" /> Access level
                </dt>
                <dd className="mt-2 text-sm font-medium">{userRole || "User"}</dd>
              </div>
            </dl>
          ) : (
            <div className="flex items-center gap-3 text-sm text-slate-500" aria-live="polite">
              <UserRound className="h-5 w-5" />
              Loading account details...
            </div>
          )}
        </section>

        <button
          type="button"
          onClick={handleLogout}
          className="inline-flex items-center gap-2 rounded-lg bg-slate-950 px-4 py-2.5 text-sm font-semibold text-white hover:bg-slate-800 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:ring-offset-2"
        >
          <LogOut className="h-4 w-4" />
          Log out securely
        </button>
      </div>
    </div>
  );
}
