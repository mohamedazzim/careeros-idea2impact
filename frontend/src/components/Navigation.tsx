"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState, useEffect, useMemo } from "react";
import {
  LayoutDashboard, BrainCircuit, Briefcase, FileText, Settings,
  BarChart3, Shield, Activity, BookOpen, Compass, ClipboardCheck,
  Gauge, Menu, X, User, LogOut, Map, Zap, Package,
  GraduationCap, GitBranch, CheckCircle, Mic
} from "lucide-react";
import { getNavSections, UserRole } from "../lib/rbac";

function safeGetRole(): UserRole | null {
  try {
    const token = localStorage.getItem('careeros_token');
    if (!token) return null;
    const payload = JSON.parse(atob(token.split('.')[1]));
    return payload.role || null;
  } catch {
    return null;
  }
}

export default function Navigation() {
  const pathname = usePathname();
  const [open, setOpen] = useState(false);
  const [role, setRole] = useState<UserRole | null>(null);

  useEffect(() => {
    setRole(safeGetRole());
  }, []);

  const navSections = useMemo(() => getNavSections(role), [role]);

  const iconMap: Record<string, React.ElementType> = {
    LayoutDashboard, BrainCircuit, Briefcase, FileText, Settings,
    BarChart3, Shield, Activity, BookOpen, Compass, ClipboardCheck,
    Gauge, Zap, Map, Package, GraduationCap, GitBranch, CheckCircle, Mic,
    User,
  };

  const logout = () => {
    try {
      localStorage.removeItem("careeros_token");
      sessionStorage.clear();
    } catch {}
    document.cookie = "careeros_token=; path=/; max-age=0; SameSite=Lax";
    window.location.replace("/login");
  };

  return (
    <>
      <button
        onClick={() => setOpen(!open)}
        className="fixed top-4 left-4 z-50 lg:hidden p-2 bg-slate-900 border border-slate-700 rounded-lg text-slate-300"
        aria-label="Toggle navigation"
      >
        {open ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
      </button>

      <nav
        className={`fixed top-0 left-0 h-full w-56 bg-slate-950 border-r border-slate-800 z-40 transform transition-transform duration-200 ${
          open ? "translate-x-0" : "-translate-x-full"
        } lg:translate-x-0 overflow-y-auto`}
        aria-label="Main navigation"
      >
        <a href="#main-content" className="sr-only focus:not-sr-only focus:absolute focus:top-2 focus:left-2 focus:bg-indigo-600 focus:text-white focus:p-2 focus:z-50 focus:rounded">
          Skip to content
        </a>
        <div className="p-4 border-b border-slate-800">
          <Link href="/dashboard" prefetch={false} className="text-sm font-bold text-white flex items-center gap-2">
            <BrainCircuit className="h-5 w-5 text-indigo-400" aria-hidden="true" />
            CareerOS AI
          </Link>
        </div>
        <div className="p-2 space-y-3">
          {navSections.map((section) => (
            <div key={section.title} className="space-y-0.5">
              <p className="px-3 pt-1 pb-1 text-[10px] font-mono uppercase tracking-[0.18em] text-slate-500">{section.title}</p>
              {section.items.map(({ href, label, icon }) => {
                const IconComponent = icon ? iconMap[icon] || Activity : Activity;
                const isActive = pathname === href || (href !== "/" && pathname.startsWith(href));
                return (
                  <Link
                    key={href}
                    href={href}
                    prefetch={false}
                    onClick={() => setOpen(false)}
                    className={`flex items-center gap-2.5 px-3 py-2 rounded-lg text-xs font-medium transition-colors ${
                      isActive
                        ? "bg-indigo-600/20 text-indigo-300 border border-indigo-500/30"
                        : "text-slate-400 hover:text-slate-200 hover:bg-slate-800/50"
                    }`}
                    aria-current={isActive ? "page" : undefined}
                  >
                    <IconComponent className="h-4 w-4 shrink-0" aria-hidden="true" />
                    {label}
                  </Link>
                );
              })}
            </div>
          ))}
          {role && (
            <div className="border-t border-slate-800 mt-2 pt-2">
              <button
                type="button"
                onClick={logout}
                className="w-full flex items-center gap-2.5 px-3 py-2 rounded-lg text-xs font-medium text-slate-400 hover:text-rose-300 hover:bg-rose-500/10 transition-colors"
              >
                <LogOut className="h-4 w-4 shrink-0" aria-hidden="true" />
                Log out
              </button>
            </div>
          )}
        </div>
      </nav>

      {open && (
        <div
          className="fixed inset-0 bg-black/50 z-30 lg:hidden"
          onClick={() => setOpen(false)}
          role="presentation"
          aria-hidden="true"
        />
      )}
    </>
  );
}
