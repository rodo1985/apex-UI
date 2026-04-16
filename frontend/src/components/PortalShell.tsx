import type { ReactNode } from "react";

import { ApexLockup } from "./Brand";
import type { PortalProfile } from "../lib/api";

export type PortalView =
  | "today"
  | "profile"
  | "products"
  | "history"
  | "trends";

const NAV_ITEMS: Array<{ label: string; value: PortalView }> = [
  { label: "Today", value: "today" },
  { label: "Profile", value: "profile" },
  { label: "Food products", value: "products" },
  { label: "History", value: "history" },
  { label: "Trends", value: "trends" },
];

/**
 * Render the main shell shared by every portal view.
 *
 * Parameters:
 *   profile: Athlete context shown in the shell.
 *   activeView: Currently selected view.
 *   onChangeView: Callback used when the user switches views.
 *   sidebarOpen: Whether the mobile sidebar drawer is visible.
 *   onToggleSidebar: Callback used by the mobile menu button.
 *   onCloseSidebar: Callback used when the sidebar should close.
 *   onLock: Optional callback used to clear the local access token.
 *   children: Active view content.
 *
 * Returns:
 *   JSX.Element: Portal shell with sidebar and main content region.
 *
 * Raises:
 *   This component does not raise errors directly.
 */
export function PortalShell({
  profile,
  activeView,
  onChangeView,
  sidebarOpen,
  onToggleSidebar,
  onCloseSidebar,
  onLock,
  children,
}: {
  profile: PortalProfile;
  activeView: PortalView;
  onChangeView: (value: PortalView) => void;
  sidebarOpen: boolean;
  onToggleSidebar: () => void;
  onCloseSidebar: () => void;
  onLock?: () => void;
  children: ReactNode;
}) {
  const activeLabel =
    NAV_ITEMS.find((item) => item.value === activeView)?.label ?? "Portal";

  return (
    <div className={`portal-shell${sidebarOpen ? " sidebar-open" : ""}`}>
      <button
        type="button"
        className={`portal-sidebar-backdrop${sidebarOpen ? " visible" : ""}`}
        onClick={onCloseSidebar}
        aria-label="Close navigation menu"
      />

      <aside className={`portal-sidebar${sidebarOpen ? " open" : ""}`}>
        <div className="portal-sidebar-block portal-sidebar-brand">
          <ApexLockup size={40} wordmarkSize={24} mode="naked" />
          <p className="portal-sidebar-kicker">Progress portal</p>
          <button
            type="button"
            className="portal-sidebar-close"
            onClick={onCloseSidebar}
            aria-label="Close navigation menu"
          >
            <span />
            <span />
          </button>
        </div>

        <nav className="portal-nav" aria-label="Portal sections">
          {NAV_ITEMS.map((item) => (
            <button
              key={item.value}
              type="button"
              className={`portal-nav-button${
                item.value === activeView ? " active" : ""
              }`}
              onClick={() => {
                onChangeView(item.value);
                onCloseSidebar();
              }}
            >
              {item.label}
            </button>
          ))}
        </nav>

        <div className="portal-sidebar-block portal-athlete-card">
          <div className="portal-athlete-avatar">
            {profile.athlete_name.slice(0, 1)}
          </div>
          <div>
            <strong>{profile.athlete_name}</strong>
            <p>{profile.ftp_watts ? `${profile.ftp_watts} W FTP` : "APEX athlete"}</p>
          </div>
        </div>

        {onLock ? (
          <button
            type="button"
            className="portal-lock-button"
            onClick={onLock}
          >
            Lock portal
          </button>
        ) : null}
      </aside>

      <main className="portal-main">
        <div className="portal-mobile-bar">
          <button
            type="button"
            className="portal-menu-button"
            aria-label={sidebarOpen ? "Close navigation menu" : "Open navigation menu"}
            aria-expanded={sidebarOpen}
            onClick={onToggleSidebar}
          >
            <span />
            <span />
            <span />
          </button>

          <div className="portal-mobile-bar-copy">
            <p className="portal-kicker">APEX Progress Review</p>
            <strong>{activeLabel}</strong>
          </div>
        </div>

        {children}
      </main>
    </div>
  );
}
