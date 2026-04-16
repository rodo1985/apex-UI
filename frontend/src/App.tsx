import { startTransition, useDeferredValue, useEffect, useState } from "react";

import { ApexLockup } from "./components/Brand";
import { PortalShell, type PortalView } from "./components/PortalShell";
import { TrendChart } from "./components/TrendChart";
import { getBootstrap, type BootstrapResponse, type DailySnapshot, type HistoryDay } from "./lib/api";
import {
  formatCalories,
  formatDistance,
  formatDuration,
  formatLongDate,
  formatShortDate,
  formatSignedValue,
  markdownToExcerpt,
} from "./lib/format";

const TOKEN_STORAGE_KEY = "apex.portal.accessToken";
const HISTORY_WINDOW_OPTIONS = [14, 28, 56, 84];
const TREND_WINDOW_OPTIONS = [28, 56, 84, 168];

type TrendMetric = "food" | "exercise" | "protein" | "load";
type ViewStatus = "loading" | "ready" | "unlock" | "error";

/**
 * Render the main APEX progress portal.
 *
 * Parameters:
 *   None.
 *
 * Returns:
 *   JSX.Element: Full single-page portal experience.
 *
 * Raises:
 *   This component does not raise errors directly.
 */
export default function App() {
  const [activeView, setActiveView] = useState<PortalView>("today");
  const [selectedDate, setSelectedDate] = useState<string>("");
  const [historyDays, setHistoryDays] = useState<number>(28);
  const [trendDays, setTrendDays] = useState<number>(84);
  const [trendMetric, setTrendMetric] = useState<TrendMetric>("food");
  const [reloadNonce, setReloadNonce] = useState<number>(0);
  const [accessToken, setAccessToken] = useState<string | null>(() =>
    typeof window === "undefined" ? null : window.sessionStorage.getItem(TOKEN_STORAGE_KEY),
  );
  const [portalData, setPortalData] = useState<BootstrapResponse | null>(null);
  const [status, setStatus] = useState<ViewStatus>("loading");
  const [errorMessage, setErrorMessage] = useState<string>("");

  useEffect(() => {
    let cancelled = false;

    async function loadPortalData() {
      setStatus("loading");
      setErrorMessage("");

      try {
        const nextData = await getBootstrap(selectedDate, historyDays, trendDays, accessToken);
        if (cancelled) {
          return;
        }

        setPortalData(nextData);
        setStatus("ready");
      } catch (error) {
        if (cancelled) {
          return;
        }

        const maybeStatus = typeof error === "object" && error !== null ? Reflect.get(error, "status") : undefined;
        const message = error instanceof Error ? error.message : "Unable to load the APEX portal.";

        if (maybeStatus === 401) {
          setPortalData(null);
          setStatus("unlock");
          setErrorMessage(message);
          return;
        }

        setPortalData(null);
        setStatus("error");
        setErrorMessage(message);
      }
    }

    void loadPortalData();

    return () => {
      cancelled = true;
    };
  }, [accessToken, historyDays, reloadNonce, selectedDate, trendDays]);

  const deferredTrendDays = useDeferredValue(portalData?.trends.days ?? []);

  if (status === "loading") {
    return <LoadingView />;
  }

  if (status === "unlock") {
    return <UnlockView errorMessage={errorMessage} onUnlock={handleUnlock} />;
  }

  if (status === "error" || !portalData) {
    return (
      <ErrorView
        errorMessage={errorMessage}
        onRetry={() => setReloadNonce((current) => current + 1)}
      />
    );
  }

  const activeDate = selectedDate || portalData.snapshot.date;

  return (
    <PortalShell
      profile={portalData.profile}
      activeView={activeView}
      onChangeView={setActiveView}
      onLock={accessToken ? handleLock : undefined}
    >
      <header className="portal-header">
        <div>
          <p className="portal-kicker">APEX Progress Review</p>
          <h1>{portalData.profile.athlete_name}'s portal</h1>
          <p className="portal-header-copy">{markdownToExcerpt(portalData.profile.profile_markdown, 180)}</p>
        </div>

        <div className="portal-header-metrics">
          <HeaderMetric
            label="Weight"
            value={
              portalData.profile.weight_kg
                ? `${portalData.profile.weight_kg.toFixed(1)} kg`
                : "Not set"
            }
          />
          <HeaderMetric
            label="Height"
            value={
              portalData.profile.height_cm
                ? `${portalData.profile.height_cm.toFixed(0)} cm`
                : "Not set"
            }
          />
          <HeaderMetric
            label="FTP"
            value={portalData.profile.ftp_watts ? `${portalData.profile.ftp_watts} W` : "Not set"}
          />
        </div>
      </header>

      {activeView === "today" ? (
        <TodayView
          snapshot={portalData.snapshot}
          selectedDate={activeDate}
          onSelectDate={setSelectedDate}
        />
      ) : null}

      {activeView === "history" ? (
        <HistoryView
          historyDays={historyDays}
          days={portalData.history.days}
          selectedDate={activeDate}
          onChangeWindow={setHistoryDays}
          onOpenDay={handleOpenHistoryDay}
        />
      ) : null}

      {activeView === "trends" ? (
        <TrendsView
          trendDays={trendDays}
          trendMetric={trendMetric}
          days={deferredTrendDays}
          summary={portalData.trends.summary}
          onChangeMetric={setTrendMetric}
          onChangeWindow={setTrendDays}
        />
      ) : null}
    </PortalShell>
  );

  /**
   * Persist a newly entered access token and trigger a reload.
   *
   * Parameters:
   *   nextToken: Token entered in the unlock screen.
   *
   * Returns:
   *   void
   *
   * Raises:
   *   This helper does not raise errors directly.
   */
  function handleUnlock(nextToken: string) {
    const trimmedToken = nextToken.trim();
    window.sessionStorage.setItem(TOKEN_STORAGE_KEY, trimmedToken);
    setAccessToken(trimmedToken);
  }

  /**
   * Clear the stored access token and return to the unlock screen.
   *
   * Parameters:
   *   None.
   *
   * Returns:
   *   void
   *
   * Raises:
   *   This helper does not raise errors directly.
   */
  function handleLock() {
    window.sessionStorage.removeItem(TOKEN_STORAGE_KEY);
    setAccessToken(null);
    setStatus("unlock");
  }

  /**
   * Open one history day in the primary review view.
   *
   * Parameters:
   *   targetDate: Business date selected from the history list.
   *
   * Returns:
   *   void
   *
   * Raises:
   *   This helper does not raise errors directly.
   */
  function handleOpenHistoryDay(targetDate: string) {
    startTransition(() => {
      setSelectedDate(targetDate);
      setActiveView("today");
    });
  }
}

/**
 * Render the initial loading screen for the portal.
 *
 * Parameters:
 *   None.
 *
 * Returns:
 *   JSX.Element: APEX-branded loading state.
 *
 * Raises:
 *   This component does not raise errors directly.
 */
function LoadingView() {
  return (
    <div className="status-screen">
      <ApexLockup size={72} wordmarkSize={34} />
      <p>Loading the latest APEX progress data...</p>
    </div>
  );
}

/**
 * Render the unlock form used when the backend requires a bearer token.
 *
 * Parameters:
 *   errorMessage: Optional backend error shown below the form.
 *   onUnlock: Callback used after the user submits a token.
 *
 * Returns:
 *   JSX.Element: Unlock screen with a single password field.
 *
 * Raises:
 *   This component does not raise errors directly.
 */
function UnlockView({
  errorMessage,
  onUnlock,
}: {
  errorMessage: string;
  onUnlock: (value: string) => void;
}) {
  const [draftToken, setDraftToken] = useState("");

  return (
    <div className="status-screen">
      <ApexLockup size={72} wordmarkSize={34} />
      <h1>Unlock the portal</h1>
      <p>Enter the access token configured for this APEX deployment.</p>
      <form
        className="unlock-form"
        onSubmit={(event) => {
          event.preventDefault();
          onUnlock(draftToken);
        }}
      >
        <input
          type="password"
          placeholder="Portal access token"
          value={draftToken}
          onChange={(event) => setDraftToken(event.target.value)}
        />
        <button type="submit">Unlock</button>
      </form>
      {errorMessage ? <p className="status-error">{errorMessage}</p> : null}
    </div>
  );
}

/**
 * Render an error state when the portal cannot load data.
 *
 * Parameters:
 *   errorMessage: Human-readable error detail.
 *   onRetry: Callback used when the user retries the request.
 *
 * Returns:
 *   JSX.Element: Error screen with retry action.
 *
 * Raises:
 *   This component does not raise errors directly.
 */
function ErrorView({
  errorMessage,
  onRetry,
}: {
  errorMessage: string;
  onRetry: () => void;
}) {
  return (
    <div className="status-screen">
      <ApexLockup size={72} wordmarkSize={34} />
      <h1>Portal temporarily unavailable</h1>
      <p>{errorMessage}</p>
      <button type="button" onClick={onRetry}>
        Retry
      </button>
    </div>
  );
}

/**
 * Render the detailed day view.
 *
 * Parameters:
 *   snapshot: Day payload returned by the backend.
 *   selectedDate: Current date shown in the date input.
 *   onSelectDate: Callback used when the user changes the date.
 *
 * Returns:
 *   JSX.Element: Day review section with metrics, meals, and activities.
 *
 * Raises:
 *   This component does not raise errors directly.
 */
function TodayView({
  snapshot,
  selectedDate,
  onSelectDate,
}: {
  snapshot: DailySnapshot;
  selectedDate: string;
  onSelectDate: (value: string) => void;
}) {
  const summary = snapshot.summary;

  return (
    <section className="portal-section">
      <div className="section-header-row">
        <div>
          <p className="section-kicker">Today</p>
          <h2>{formatLongDate(snapshot.date)}</h2>
          <p className="section-copy">
            Daily targets, logged meals, and completed activities in one review
            surface.
          </p>
        </div>

        <label className="date-picker">
          <span>Date</span>
          <input
            type="date"
            value={selectedDate}
            onChange={(event) => onSelectDate(event.target.value)}
          />
        </label>
      </div>

      <div className="metric-grid">
        <MetricCard
          title="Food"
          primary={formatCalories(summary.actual_food_calories)}
          secondary={
            summary.target_food_calories
              ? `Target ${formatCalories(summary.target_food_calories)}`
              : "Target pending"
          }
        />
        <MetricCard
          title="Exercise"
          primary={formatCalories(summary.actual_exercise_calories)}
          secondary={
            summary.activities_count
              ? `${summary.activities_count} activities logged`
              : "No activities yet"
          }
        />
        <MetricCard
          title="Net"
          primary={formatCalories(summary.net_calories)}
          secondary={
            summary.net_calories <= 0
              ? "Deficit day so far"
              : "Positive net intake"
          }
        />
        <MetricCard
          title="Protein"
          primary={`${Math.round(summary.actual_protein_g)} g`}
          secondary={
            summary.target_protein_g
              ? `Target ${Math.round(summary.target_protein_g)} g`
              : "Target pending"
          }
        />
      </div>

      <div className="progress-grid">
        <ProgressPanel
          title="Food calories"
          current={summary.actual_food_calories}
          target={summary.target_food_calories}
          remainder={summary.remaining_food_calories}
          unit="kcal"
        />
        <ProgressPanel
          title="Protein"
          current={summary.actual_protein_g}
          target={summary.target_protein_g}
          remainder={summary.remaining_protein_g}
          unit="g"
        />
        <ProgressPanel
          title="Carbs"
          current={summary.actual_carbs_g}
          target={summary.target_carbs_g}
          remainder={summary.remaining_carbs_g}
          unit="g"
        />
        <ProgressPanel
          title="Fat"
          current={summary.actual_fat_g}
          target={summary.target_fat_g}
          remainder={summary.remaining_fat_g}
          unit="g"
        />
      </div>

      <div className="split-grid">
        <div className="panel">
          <div className="panel-header">
            <h3>Meals</h3>
            <span>{summary.meal_items_count} items</span>
          </div>

          {snapshot.meals.length === 0 ? (
            <EmptyPanel message="No meals logged for this day yet." />
          ) : (
            <div className="meal-list">
              {snapshot.meals.map((meal) => (
                <article key={meal.id} className="meal-card">
                  <div className="meal-card-header">
                    <div>
                      <h4>{meal.meal_label}</h4>
                      <p>{formatCalories(meal.total_calories)}</p>
                    </div>
                    <div className="meal-totals">
                      <span>{Math.round(meal.total_protein_g)}P</span>
                      <span>{Math.round(meal.total_carbs_g)}C</span>
                      <span>{Math.round(meal.total_fat_g)}F</span>
                    </div>
                  </div>

                  <ul className="meal-items">
                    {meal.items.map((item) => (
                      <li key={item.id}>
                        <div>
                          <strong>{item.ingredient_name}</strong>
                          <span>{Math.round(item.grams)} g</span>
                        </div>
                        <span>{formatCalories(item.calories)}</span>
                      </li>
                    ))}
                  </ul>
                </article>
              ))}
            </div>
          )}
        </div>

        <div className="panel">
          <div className="panel-header">
            <h3>Activities</h3>
            <span>{summary.activities_count} logged</span>
          </div>

          {snapshot.activities.length === 0 ? (
            <EmptyPanel message="No activities logged for this day yet." />
          ) : (
            <div className="activity-list">
              {snapshot.activities.map((activity) => (
                <article key={activity.id} className="activity-card">
                  <div className="activity-card-header">
                    <div>
                      <h4>{activity.title}</h4>
                      <p>
                        {activity.sport_type ?? "Activity"}
                        {activity.external_source
                          ? ` • ${activity.external_source}`
                          : ""}
                      </p>
                    </div>
                    <strong>{formatCalories(activity.calories)}</strong>
                  </div>

                  <div className="activity-stats">
                    <span>{formatDistance(activity.distance_meters)}</span>
                    <span>{formatDuration(activity.moving_time_seconds)}</span>
                    <span>
                      {activity.total_elevation_gain_meters
                        ? `${Math.round(activity.total_elevation_gain_meters)} m+`
                        : "0 m+"}
                    </span>
                    <span>
                      {activity.average_heartrate
                        ? `${Math.round(activity.average_heartrate)} bpm`
                        : "HR n/a"}
                    </span>
                  </div>

                  {activity.notes_markdown ? (
                    <p className="activity-note">{activity.notes_markdown}</p>
                  ) : null}
                </article>
              ))}
            </div>
          )}
        </div>
      </div>
    </section>
  );
}

/**
 * Render the day history list.
 *
 * Parameters:
 *   historyDays: Active history window size.
 *   days: Day summaries returned by the backend.
 *   selectedDate: Date currently open in the Today view.
 *   onChangeWindow: Callback used when the history window changes.
 *   onOpenDay: Callback used when the user opens a day in the Today view.
 *
 * Returns:
 *   JSX.Element: History panel with window controls and day list.
 *
 * Raises:
 *   This component does not raise errors directly.
 */
function HistoryView({
  historyDays,
  days,
  selectedDate,
  onChangeWindow,
  onOpenDay,
}: {
  historyDays: number;
  days: HistoryDay[];
  selectedDate: string;
  onChangeWindow: (value: number) => void;
  onOpenDay: (targetDate: string) => void;
}) {
  return (
    <section className="portal-section">
      <div className="section-header-row">
        <div>
          <p className="section-kicker">History</p>
          <h2>Past logged days</h2>
          <p className="section-copy">
            Review the days that already carry targets, meals, or activities.
          </p>
        </div>

        <WindowSelector
          label="Window"
          activeValue={historyDays}
          values={HISTORY_WINDOW_OPTIONS}
          onChange={onChangeWindow}
        />
      </div>

      <div className="panel">
        <div className="history-table">
          {days.length === 0 ? (
            <EmptyPanel message="No tracked days were found in this history window." />
          ) : (
            days.map((day) => (
              <button
                key={day.date}
                type="button"
                className={`history-row${day.date === selectedDate ? " active" : ""}`}
                onClick={() => onOpenDay(day.date)}
              >
                <div className="history-row-primary">
                  <strong>{formatLongDate(day.date)}</strong>
                  <span>
                    {day.meals_count} meals • {day.activities_count} activities
                  </span>
                </div>
                <div className="history-row-metrics">
                  <span>{formatCalories(day.actual_food_calories)}</span>
                  <span>{formatCalories(day.actual_exercise_calories)}</span>
                  <span>{formatDistance(day.total_distance_meters)}</span>
                  <span>{formatSignedValue(day.net_calories, "kcal")}</span>
                </div>
              </button>
            ))
          )}
        </div>
      </div>
    </section>
  );
}

/**
 * Render the trends section with chart and summary metrics.
 *
 * Parameters:
 *   trendDays: Active trend window size.
 *   trendMetric: Selected metric for the chart.
 *   days: Chronological trend days.
 *   summary: Rolled-up window metrics.
 *   onChangeMetric: Callback used when the metric changes.
 *   onChangeWindow: Callback used when the window changes.
 *
 * Returns:
 *   JSX.Element: Trends panel with chart and summary tiles.
 *
 * Raises:
 *   This component does not raise errors directly.
 */
function TrendsView({
  trendDays,
  trendMetric,
  days,
  summary,
  onChangeMetric,
  onChangeWindow,
}: {
  trendDays: number;
  trendMetric: TrendMetric;
  days: HistoryDay[];
  summary: BootstrapResponse["trends"]["summary"];
  onChangeMetric: (value: TrendMetric) => void;
  onChangeWindow: (value: number) => void;
}) {
  const metricMeta = getTrendMetricMeta(trendMetric);
  const chartValues = days.map((day) => metricMeta.pickValue(day));
  const chartLabels = days.map((day) => formatShortDate(day.date));

  return (
    <section className="portal-section">
      <div className="section-header-row">
        <div>
          <p className="section-kicker">Evolution</p>
          <h2>Longer-term trends</h2>
          <p className="section-copy">
            Follow how fuelling and training output are evolving over the
            selected window.
          </p>
        </div>

        <WindowSelector
          label="Window"
          activeValue={trendDays}
          values={TREND_WINDOW_OPTIONS}
          onChange={onChangeWindow}
        />
      </div>

      <div className="trend-toolbar">
        {(["food", "exercise", "protein", "load"] as TrendMetric[]).map(
          (metric) => (
            <button
              key={metric}
              type="button"
              className={`trend-toggle${metric === trendMetric ? " active" : ""}`}
              onClick={() => onChangeMetric(metric)}
            >
              {getTrendMetricMeta(metric).label}
            </button>
          ),
        )}
      </div>

      <div className="panel">
        <div className="panel-header">
          <h3>{metricMeta.label}</h3>
          <span>{metricMeta.subtitle}</span>
        </div>
        <TrendChart
          values={chartValues}
          labels={chartLabels}
          accent={metricMeta.color}
        />
      </div>

      <div className="metric-grid">
        <MetricCard
          title="Logged days"
          primary={String(summary.logged_days)}
          secondary="Days with any tracked data"
        />
        <MetricCard
          title="Avg food"
          primary={formatCalories(summary.average_food_calories)}
          secondary="Average intake across logged days"
        />
        <MetricCard
          title="Avg exercise"
          primary={formatCalories(summary.average_exercise_calories)}
          secondary="Average exercise burn across logged days"
        />
        <MetricCard
          title="Total distance"
          primary={formatDistance(summary.total_distance_meters)}
          secondary={`${summary.total_activities} activities in window`}
        />
      </div>
    </section>
  );
}

/**
 * Render one compact metric tile.
 *
 * Parameters:
 *   title: Label shown above the main value.
 *   primary: Main numeric or status value.
 *   secondary: Supporting context shown below the main value.
 *
 * Returns:
 *   JSX.Element: Small metric panel.
 *
 * Raises:
 *   This component does not raise errors directly.
 */
function MetricCard({
  title,
  primary,
  secondary,
}: {
  title: string;
  primary: string;
  secondary: string;
}) {
  return (
    <article className="metric-card">
      <p>{title}</p>
      <strong>{primary}</strong>
      <span>{secondary}</span>
    </article>
  );
}

/**
 * Render a compact header metric chip.
 *
 * Parameters:
 *   label: Metric label.
 *   value: Metric value.
 *
 * Returns:
 *   JSX.Element: Small header metric.
 *
 * Raises:
 *   This component does not raise errors directly.
 */
function HeaderMetric({ label, value }: { label: string; value: string }) {
  return (
    <div className="header-metric">
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

/**
 * Render one progress block for a target-based metric.
 *
 * Parameters:
 *   title: Metric label.
 *   current: Current logged value.
 *   target: Optional target value.
 *   remainder: Optional remaining value.
 *   unit: Unit suffix used for labels.
 *
 * Returns:
 *   JSX.Element: Progress panel with bar and supporting labels.
 *
 * Raises:
 *   This component does not raise errors directly.
 */
function ProgressPanel({
  title,
  current,
  target,
  remainder,
  unit,
}: {
  title: string;
  current: number;
  target: number | null;
  remainder: number | null;
  unit: "kcal" | "g";
}) {
  const progress = target ? Math.min((current / target) * 100, 100) : 0;

  return (
    <article className="progress-panel">
      <div className="panel-header">
        <h3>{title}</h3>
        <span>
          {target ? `Target ${Math.round(target)} ${unit}` : "No target"}
        </span>
      </div>
      <strong>
        {Math.round(current)} {unit}
      </strong>
      <div className="progress-track" aria-hidden="true">
        <div className="progress-fill" style={{ width: `${progress}%` }} />
      </div>
      <p>
        {remainder === null
          ? "Target not set yet."
          : `${Math.round(remainder)} ${unit} remaining`}
      </p>
    </article>
  );
}

/**
 * Render an empty panel placeholder.
 *
 * Parameters:
 *   message: Empty-state message shown to the user.
 *
 * Returns:
 *   JSX.Element: Simple empty-state container.
 *
 * Raises:
 *   This component does not raise errors directly.
 */
function EmptyPanel({ message }: { message: string }) {
  return <div className="empty-panel">{message}</div>;
}

/**
 * Render a numeric window selector used by the history and trends views.
 *
 * Parameters:
 *   label: Visible label for the control.
 *   activeValue: Currently selected value.
 *   values: Allowed numeric options.
 *   onChange: Callback used when the user selects a new option.
 *
 * Returns:
 *   JSX.Element: Compact segmented control.
 *
 * Raises:
 *   This component does not raise errors directly.
 */
function WindowSelector({
  label,
  activeValue,
  values,
  onChange,
}: {
  label: string;
  activeValue: number;
  values: number[];
  onChange: (value: number) => void;
}) {
  return (
    <div className="window-selector">
      <span>{label}</span>
      <div>
        {values.map((value) => (
          <button
            key={value}
            type="button"
            className={value === activeValue ? "active" : ""}
            onClick={() => onChange(value)}
          >
            {value}d
          </button>
        ))}
      </div>
    </div>
  );
}

/**
 * Return the display configuration for one trend metric.
 *
 * Parameters:
 *   metric: Selected trend metric key.
 *
 * Returns:
 *   Object with label, subtitle, color, and value picker.
 *
 * Raises:
 *   This helper does not raise errors directly.
 */
function getTrendMetricMeta(metric: TrendMetric) {
  if (metric === "exercise") {
    return {
      label: "Exercise calories",
      subtitle: "Daily logged exercise burn",
      color: "#60A5FA",
      pickValue: (day: HistoryDay) => day.actual_exercise_calories,
    };
  }

  if (metric === "protein") {
    return {
      label: "Protein intake",
      subtitle: "Daily protein intake in grams",
      color: "#F97316",
      pickValue: (day: HistoryDay) => day.actual_protein_g,
    };
  }

  if (metric === "load") {
    return {
      label: "Training load",
      subtitle: "Daily suffer score from logged activities",
      color: "#FB7185",
      pickValue: (day: HistoryDay) => day.total_suffer_score,
    };
  }

  return {
    label: "Food calories",
    subtitle: "Daily logged food intake",
    color: "#2DD4BF",
    pickValue: (day: HistoryDay) => day.actual_food_calories,
  };
}
