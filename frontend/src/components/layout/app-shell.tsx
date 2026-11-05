"use client";

import * as Dialog from "@radix-ui/react-dialog";
import {
  Activity,
  AlertTriangle,
  Clock3,
  FileSearch,
  Files,
  LayoutDashboard,
  Menu,
  Network,
  LogOut,
  PanelLeftClose,
  PanelLeftOpen,
  PieChart,
  Settings,
  X,
} from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { type ReactNode, useState } from "react";

import { Button } from "@/components/ui/button";
import { AssistantChat } from "@/features/assistant/assistant-chat";
import { LoginScreen } from "@/features/auth/auth-screen";
import { useCurrentUser, useLogout } from "@/features/auth/queries";
import type { CurrentUser } from "@/lib/api/contracts";
import { cn } from "@/lib/utils";

const navigation = [
  {
    label: "Pilotage",
    items: [
      { href: "/", label: "Vue d’ensemble", icon: LayoutDashboard },
      { href: "/delays", label: "Flux & délais", icon: Clock3 },
      { href: "/agencies", label: "Réseau", icon: Network },
      { href: "/rejections", label: "Rejets", icon: AlertTriangle },
      { href: "/activities", label: "Activités", icon: Activity },
      { href: "/products-requests", label: "Produits & demandes", icon: PieChart },
    ],
  },
  {
    label: "Opérations",
    items: [
      { href: "/applications", label: "Dossiers", icon: FileSearch },
      { href: "/imports", label: "Imports & qualité", icon: Files },
      { href: "/alerts", label: "Alertes de délai", icon: AlertTriangle },
      { href: "/reference-data", label: "Référentiels", icon: Settings },
    ],
  },
] as const;

function canNavigate(user: CurrentUser, href: string) {
  if (href === "/imports") return user.capabilities.can_import;
  if (href === "/reference-data") return user.capabilities.can_manage_reference_data ?? false;
  return true;
}

function Navigation({
  user,
  onNavigate,
  collapsed = false,
}: {
  user: CurrentUser;
  onNavigate?: () => void;
  collapsed?: boolean;
}) {
  const pathname = usePathname();
  return (
    <nav aria-label="Navigation principale" className={cn("space-y-7", collapsed && "space-y-5")}>
      {navigation.map((section) => (
        <section key={section.label}>
          <p
            className={cn(
              "mb-2 px-3 text-xs font-extrabold uppercase tracking-[0.14em] !text-emerald-100",
              collapsed && "sr-only",
            )}
          >
            {section.label}
          </p>
          <div className="space-y-1">
            {section.items
              .filter(({ href }) => canNavigate(user, href))
              .map(({ href, label, icon: Icon }) => {
                const active = href === "/" ? pathname === href : pathname.startsWith(href);
                return (
                  <Link
                    aria-current={active ? "page" : undefined}
                    className={cn(
                      "flex min-h-10 items-center gap-3 rounded-lg px-3 py-2 text-[0.95rem] font-semibold !text-white transition focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-white",
                      collapsed && "justify-center px-2",
                      active
                        ? "bg-emerald-500 !text-white"
                        : "bg-white/5 !text-white hover:bg-white/20 hover:!text-white",
                    )}
                    href={href}
                    key={href}
                    onClick={onNavigate}
                    title={collapsed ? label : undefined}
                  >
                    <Icon aria-hidden="true" className="!text-white" size={18} />
                    <span className={collapsed ? "sr-only" : "!text-white"}>{label}</span>
                  </Link>
                );
              })}
          </div>
        </section>
      ))}
    </nav>
  );
}

export function AppShell({ children }: { children: ReactNode }) {
  const [open, setOpen] = useState(false);
  const [collapsed, setCollapsed] = useState(false);
  const currentUser = useCurrentUser();
  const logout = useLogout();
  if (currentUser.isLoading) {
    return (
      <main className="grid min-h-screen place-items-center bg-slate-950 text-sm font-semibold text-white">
        Checking secure session…
      </main>
    );
  }
  if (currentUser.isError || !currentUser.data) return <LoginScreen />;
  const user = currentUser.data;
  return (
    <div
      className={cn(
        "min-h-screen lg:grid",
        collapsed ? "lg:grid-cols-[5rem_minmax(0,1fr)]" : "lg:grid-cols-[17rem_minmax(0,1fr)]",
      )}
    >
      <a
        className="fixed left-3 top-3 z-[100] -translate-y-24 rounded-lg bg-white px-4 py-2 font-semibold shadow-lg focus:translate-y-0"
        href="#main-content"
      >
        Skip to content
      </a>

      <aside
        className={cn(
          "fixed inset-y-0 left-0 z-40 hidden flex-col bg-slate-950 py-5 transition-[width,padding] duration-200 lg:flex",
          collapsed ? "w-20 px-3" : "w-[17rem] px-4",
        )}
      >
        <div className={cn("flex items-center", collapsed ? "justify-center" : "justify-end px-2")}>
          <Button
            aria-label={collapsed ? "Expand navigation" : "Collapse navigation"}
            className={cn(
              "border border-white/15 bg-white/10 text-white hover:bg-white/20 hover:text-white",
              collapsed && "absolute -right-4 top-5 border border-slate-700 bg-slate-950 shadow-md",
            )}
            onClick={() => setCollapsed((value) => !value)}
            size="icon"
            variant="ghost"
          >
            {collapsed ? (
              <PanelLeftOpen aria-hidden="true" size={19} />
            ) : (
              <PanelLeftClose aria-hidden="true" size={19} />
            )}
          </Button>
        </div>
        <div className="mt-8 flex-1 overflow-y-auto">
          <Navigation collapsed={collapsed} user={user} />
        </div>
      </aside>

      <div className="min-w-0 lg:col-start-2">
        <header className="sticky top-0 z-30 flex min-h-16 items-center justify-between border-b border-[var(--border)] bg-white/95 px-4 backdrop-blur sm:px-6 lg:px-8">
          <div className="flex items-center gap-3 lg:hidden">
            <Dialog.Root onOpenChange={setOpen} open={open}>
              <Dialog.Trigger asChild>
                <Button aria-label="Open navigation" size="icon" variant="secondary">
                  <Menu aria-hidden="true" size={20} />
                </Button>
              </Dialog.Trigger>
              <Dialog.Portal>
                <Dialog.Overlay className="fixed inset-0 z-50 bg-slate-950/60 backdrop-blur-sm" />
                <Dialog.Content className="fixed inset-y-0 left-0 z-50 w-[min(88vw,20rem)] overflow-y-auto bg-slate-950 p-5 shadow-2xl focus:outline-none">
                  <div className="flex justify-end">
                    <Dialog.Title className="sr-only">Main navigation</Dialog.Title>
                    <Dialog.Description className="sr-only">
                      Navigate between Credit Operations Platform analytics and operations pages.
                    </Dialog.Description>
                    <Dialog.Close asChild>
                      <Button
                        aria-label="Close navigation"
                        className="text-white"
                        size="icon"
                        variant="ghost"
                      >
                        <X aria-hidden="true" size={20} />
                      </Button>
                    </Dialog.Close>
                  </div>
                  <div className="mt-8">
                    <Navigation onNavigate={() => setOpen(false)} user={user} />
                  </div>
                </Dialog.Content>
              </Dialog.Portal>
            </Dialog.Root>
            <span className="font-bold text-slate-900">Credit Operations Platform</span>
          </div>
          <div className="flex min-w-0 items-center gap-2 text-right">
            <span
              className={`size-2 shrink-0 rounded-full ${currentUser.isSuccess ? "bg-emerald-500" : "bg-amber-500"}`}
              aria-hidden="true"
            />
            <span className="min-w-0 text-xs text-slate-600">
              <span className="block truncate font-semibold">{user.username}</span>
              <span className="block truncate text-[var(--muted)]">Utilisateur</span>
            </span>
            <Button
              aria-label="Sign out"
              disabled={logout.isPending}
              onClick={() => logout.mutate()}
              size="icon"
              variant="ghost"
            >
              <LogOut aria-hidden="true" size={18} />
            </Button>
          </div>
        </header>
        <main
          className="mx-auto w-full max-w-[100rem] px-4 py-7 sm:px-6 lg:px-8 lg:py-9"
          id="main-content"
          tabIndex={-1}
        >
          {children}
        </main>
        <AssistantChat />
      </div>
    </div>
  );
}
