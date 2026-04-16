import type { ReactNode } from "react";

import { ApexLockup } from "./Brand";
import type { PortalProfile } from "../lib/api";
import { markdownToExcerpt } from "../lib/format";

export type PortalView = "today" | "history" | "trends";

const NAV_ITEMS: Array<{ label: string; value: PortalView }> = [
  { label: "Today", value: "today" },
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
  onLock,
  children,
}: {
  profile: PortalProfile;
  activeView: PortalView;
  onChangeView: (value: PortalView) => void;
  onLock?: () => void;
  children: ReactNode;
}) {
  return (
    <div className="portal-shell">
      <aside className="portal-sidebar">
        <div className="portal-sidebar-block">
          <ApexLockup size={40} wordmarkSize={24} mode="naked" />
          <p className="portal-sidebar-kicker">Progress portal</p>
        </div>

        <nav className="portal-nav" aria-label="Portal sections">
          {NAV_ITEMS.map((item) => (
            <button
              key={item.value}
              type="button"
              className={`portal-nav-button${
                item.value === activeView ? " active" : ""
              }`}
              onClick={() => onChangeView(item.value)}
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

        <div className="portal-sidebar-block">
          <p className="portal-sidebar-label">Focus</p>
          <p className="portal-sidebar-copy">
            {markdownToExcerpt(profile.training_goals_markdown, 120)}
          </p>
        </div>

        <div className="portal-sidebar-block">
          <p className="portal-sidebar-label">Fueling</p>
          <p className="portal-sidebar-copy">
            {markdownToExcerpt(profile.diet_goals_markdown, 120)}
          </p>
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

      <main className="portal-main">{children}</main>
    </div>
  );
}
