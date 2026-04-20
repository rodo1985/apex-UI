import type { ReactNode } from "react";

import { ApexLockup } from "./Brand";

export type PortalView =
  | "today"
  | "trends"
  | "products"
  | "history"
  | "profile";

const NAV_ITEMS: Array<{
  label: string;
  value: PortalView;
  icon: ReactNode;
}> = [
  { label: "Today", value: "today", icon: <TodayIcon /> },
  { label: "Trends", value: "trends", icon: <TrendsIcon /> },
  { label: "Food products", value: "products", icon: <FoodProductsIcon /> },
  { label: "History", value: "history", icon: <HistoryIcon /> },
  { label: "Profile", value: "profile", icon: <ProfileIcon /> },
];

/**
 * Render the main shell shared by every portal view.
 *
 * Parameters:
 *   activeView: Currently selected view.
 *   isCompactLayout: Whether the compact drawer layout is active.
 *   sidebarVisible: Whether the sidebar is currently visible.
 *   onChangeView: Callback used when the user switches views.
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
  activeView,
  isCompactLayout,
  sidebarVisible,
  onChangeView,
  onToggleSidebar,
  onCloseSidebar,
  onLock,
  children,
}: {
  activeView: PortalView;
  isCompactLayout: boolean;
  sidebarVisible: boolean;
  onChangeView: (value: PortalView) => void;
  onToggleSidebar: () => void;
  onCloseSidebar: () => void;
  onLock?: () => void;
  children: ReactNode;
}) {
  const activeLabel =
    NAV_ITEMS.find((item) => item.value === activeView)?.label ?? "Portal";
  const isSidebarCollapsed = !isCompactLayout && !sidebarVisible;
  const shellStateClass = isCompactLayout
    ? sidebarVisible
      ? " sidebar-open"
      : " sidebar-hidden"
    : sidebarVisible
      ? " sidebar-open"
      : " sidebar-collapsed";

  return (
    <div
      className={`portal-shell${shellStateClass}${isCompactLayout ? " compact-layout" : ""}`}
    >
      <button
        type="button"
        className={`portal-sidebar-backdrop${
          isCompactLayout && sidebarVisible ? " visible" : ""
        }`}
        onClick={onCloseSidebar}
        aria-label="Close navigation menu"
      />

      <aside
        className={`portal-sidebar${isCompactLayout ? (sidebarVisible ? " open" : "") : " open"}${
          isSidebarCollapsed ? " collapsed" : ""
        }`}
      >
        <div className="portal-sidebar-block portal-sidebar-brand">
          <div className="portal-sidebar-brand-copy">
            <ApexLockup size={40} wordmarkSize={24} mode="naked" />
            <p className="portal-sidebar-kicker">Progress review</p>
          </div>

          {isCompactLayout ? (
            <button
              type="button"
              className="portal-sidebar-close"
              onClick={onCloseSidebar}
              aria-label="Close navigation menu"
            >
              <span />
              <span />
            </button>
          ) : null}
        </div>

        <nav className="portal-nav" aria-label="Portal sections">
          {NAV_ITEMS.map((item) => (
            <button
              key={item.value}
              type="button"
              className={`portal-nav-button${
                item.value === activeView ? " active" : ""
              }`}
              title={isSidebarCollapsed ? item.label : undefined}
              onClick={() => {
                onChangeView(item.value);
                if (isCompactLayout) {
                  onCloseSidebar();
                }
              }}
            >
              <span className="portal-nav-icon" aria-hidden="true">
                {item.icon}
              </span>
              <span className="portal-nav-label">{item.label}</span>
            </button>
          ))}
        </nav>

        {onLock ? (
          <button
            type="button"
            className="portal-lock-button"
            onClick={onLock}
            title={isSidebarCollapsed ? "Log out" : undefined}
          >
            <span className="portal-lock-icon" aria-hidden="true">
              <LogoutIcon />
            </span>
            <span className="portal-lock-label">Log out</span>
          </button>
        ) : null}
      </aside>

      <main className="portal-main">
        <div className="portal-top-bar">
          <button
            type="button"
            className="portal-menu-button"
            aria-label={
              sidebarVisible
                ? "Collapse navigation menu"
                : "Expand navigation menu"
            }
            aria-expanded={sidebarVisible}
            onClick={onToggleSidebar}
          >
            <span className="portal-menu-icon" aria-hidden="true">
              <span className="portal-menu-icon-rail" />
              <span className="portal-menu-icon-stack">
                <span className="portal-menu-icon-line" />
                <span className="portal-menu-icon-line" />
                <span className="portal-menu-icon-line" />
              </span>
            </span>
          </button>

          <div className="portal-top-bar-copy">
            <p className="portal-kicker">APEX Progress Review</p>
            <strong>{activeLabel}</strong>
          </div>
        </div>

        {children}
      </main>
    </div>
  );
}

/**
 * Render the logout action icon.
 *
 * Parameters:
 *   None.
 *
 * Returns:
 *   JSX.Element: Small exit icon for the sidebar action button.
 *
 * Raises:
 *   This component does not raise errors directly.
 */
function LogoutIcon() {
  return (
    <svg viewBox="0 0 20 20" fill="none">
      <path
        d="M8 4.5H6a1.5 1.5 0 0 0-1.5 1.5v8A1.5 1.5 0 0 0 6 15.5h2"
        stroke="currentColor"
        strokeWidth="1.5"
        strokeLinecap="round"
      />
      <path
        d="M10.5 6.5 14 10l-3.5 3.5M14 10H8"
        stroke="currentColor"
        strokeWidth="1.5"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

/**
 * Render the "Today" navigation icon.
 *
 * Parameters:
 *   None.
 *
 * Returns:
 *   JSX.Element: Small home-shaped icon for the sidebar.
 *
 * Raises:
 *   This component does not raise errors directly.
 */
function TodayIcon() {
  return (
    <svg viewBox="0 0 20 20" fill="none">
      <path
        d="M3.5 8.5 10 3.5l6.5 5v7a1 1 0 0 1-1 1h-3.5v-4h-4v4H4.5a1 1 0 0 1-1-1z"
        stroke="currentColor"
        strokeWidth="1.5"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

/**
 * Render the profile navigation icon.
 *
 * Parameters:
 *   None.
 *
 * Returns:
 *   JSX.Element: Small user-shaped icon for the sidebar.
 *
 * Raises:
 *   This component does not raise errors directly.
 */
function ProfileIcon() {
  return (
    <svg viewBox="0 0 20 20" fill="none">
      <circle cx="10" cy="6.25" r="2.75" stroke="currentColor" strokeWidth="1.5" />
      <path
        d="M4.5 16c.7-2.25 2.7-3.75 5.5-3.75s4.8 1.5 5.5 3.75"
        stroke="currentColor"
        strokeWidth="1.5"
        strokeLinecap="round"
      />
    </svg>
  );
}

/**
 * Render the food products navigation icon.
 *
 * Parameters:
 *   None.
 *
 * Returns:
 *   JSX.Element: Small nutrition list icon for the sidebar.
 *
 * Raises:
 *   This component does not raise errors directly.
 */
function FoodProductsIcon() {
  return (
    <svg viewBox="0 0 20 20" fill="none">
      <path
        d="M6 4.5h8M6 10h8M6 15.5h8"
        stroke="currentColor"
        strokeWidth="1.5"
        strokeLinecap="round"
      />
      <circle cx="4" cy="4.5" r="1" fill="currentColor" />
      <circle cx="4" cy="10" r="1" fill="currentColor" />
      <circle cx="4" cy="15.5" r="1" fill="currentColor" />
    </svg>
  );
}

/**
 * Render the history navigation icon.
 *
 * Parameters:
 *   None.
 *
 * Returns:
 *   JSX.Element: Small calendar icon for the sidebar.
 *
 * Raises:
 *   This component does not raise errors directly.
 */
function HistoryIcon() {
  return (
    <svg viewBox="0 0 20 20" fill="none">
      <rect
        x="3.5"
        y="4.5"
        width="13"
        height="12"
        rx="2"
        stroke="currentColor"
        strokeWidth="1.5"
      />
      <path
        d="M3.5 8h13M7 3.5v2M13 3.5v2"
        stroke="currentColor"
        strokeWidth="1.5"
        strokeLinecap="round"
      />
    </svg>
  );
}

/**
 * Render the trends navigation icon.
 *
 * Parameters:
 *   None.
 *
 * Returns:
 *   JSX.Element: Small chart icon for the sidebar.
 *
 * Raises:
 *   This component does not raise errors directly.
 */
function TrendsIcon() {
  return (
    <svg viewBox="0 0 20 20" fill="none">
      <path
        d="M4 14.5 8 10.5l3 2 5-6"
        stroke="currentColor"
        strokeWidth="1.5"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <path
        d="M4 4.5v10h12"
        stroke="currentColor"
        strokeWidth="1.5"
        strokeLinecap="round"
      />
    </svg>
  );
}
