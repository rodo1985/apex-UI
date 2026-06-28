import { startTransition, useDeferredValue, useEffect, useState } from "react";

import { ApexLockup } from "./components/Brand";
import { MarkdownContent } from "./components/MarkdownContent";
import { PortalShell, type PortalView } from "./components/PortalShell";
import { TrendChart } from "./components/TrendChart";
import {
  getBootstrap,
  getPlan,
  getPlanComparison,
  getPlans,
  getProducts,
  type BootstrapResponse,
  type DailySnapshot,
  type DailyMetricSeries,
  type FoodProduct,
  type FoodProductsResponse,
  type HistoryDay,
  type PortalProfile,
  type TrainingPlanComparisonResponse,
  type TrainingPlanDay,
  type TrainingPlanDetail,
  type TrainingPlansResponse,
} from "./lib/api";
import {
  formatCalories,
  formatDistance,
  formatDuration,
  formatLongDate,
  formatSignedValue,
  formatShortDate,
  shiftIsoDate,
  todayIsoDate,
} from "./lib/format";

const TOKEN_STORAGE_KEY = "apex.portal.accessToken";
const DEFAULT_ACCESS_TOKEN = import.meta.env.VITE_PORTAL_ACCESS_TOKEN ?? null;
const HISTORY_WINDOW_OPTIONS = [14, 28, 56, 84];
const TREND_WINDOW_OPTIONS = [7, 30, 90, 365];
const BUILT_IN_TREND_METRICS = [
  "food",
  "exercise",
  "protein",
  "carbs",
  "fat",
  "load",
] as const;
const DAILY_METRIC_COLORS = [
  "#A78BFA",
  "#F472B6",
  "#34D399",
  "#F59E0B",
  "#38BDF8",
  "#F87171",
] as const;

type BuiltInTrendMetric = (typeof BUILT_IN_TREND_METRICS)[number];
type DailyTrendMetric = `daily_metric:${string}`;
type TrendMetric = BuiltInTrendMetric | DailyTrendMetric;
type ProgressTone = "food" | "protein" | "carbs" | "fat";
type ProductsSortKey =
  | "name"
  | "default_serving_g"
  | "calories_per_100g"
  | "carbs_g_per_100g"
  | "protein_g_per_100g"
  | "fat_g_per_100g"
  | "usage_count";
type SortDirection = "asc" | "desc";
type ViewStatus = "loading" | "ready" | "unlock" | "error";
type ProductsStatus = "idle" | "loading" | "ready" | "error";
type PlansStatus = "idle" | "loading" | "ready" | "error";
type PlanPanel = "calendar" | "comparison";

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
  const [isCompactLayout, setIsCompactLayout] = useState<boolean>(() =>
    readCompactLayoutPreference(),
  );
  const [activeView, setActiveView] = useState<PortalView>("today");
  const [selectedDate, setSelectedDate] = useState<string>("");
  const [historyDays, setHistoryDays] = useState<number>(28);
  const [trendDays, setTrendDays] = useState<number>(90);
  const [trendMetric, setTrendMetric] = useState<TrendMetric>("food");
  const [reloadNonce, setReloadNonce] = useState<number>(0);
  const [sidebarVisible, setSidebarVisible] = useState<boolean>(() =>
    readDefaultSidebarVisibility(),
  );
  const [accessToken, setAccessToken] = useState<string | null>(() =>
    typeof window === "undefined"
      ? DEFAULT_ACCESS_TOKEN
      : window.sessionStorage.getItem(TOKEN_STORAGE_KEY) ?? DEFAULT_ACCESS_TOKEN,
  );
  const [portalData, setPortalData] = useState<BootstrapResponse | null>(null);
  const [status, setStatus] = useState<ViewStatus>("loading");
  const [errorMessage, setErrorMessage] = useState<string>("");
  const [productsData, setProductsData] = useState<FoodProductsResponse | null>(
    null,
  );
  const [productsStatus, setProductsStatus] =
    useState<ProductsStatus>("idle");
  const [productsErrorMessage, setProductsErrorMessage] = useState<string>("");
  const [productsReloadNonce, setProductsReloadNonce] = useState<number>(0);
  const [plansData, setPlansData] = useState<TrainingPlansResponse | null>(
    null,
  );
  const [plansStatus, setPlansStatus] = useState<PlansStatus>("idle");
  const [plansErrorMessage, setPlansErrorMessage] = useState<string>("");
  const [plansReloadNonce, setPlansReloadNonce] = useState<number>(0);
  const [selectedPlanId, setSelectedPlanId] = useState<number | null>(null);
  const [planDetail, setPlanDetail] = useState<TrainingPlanDetail | null>(null);
  const [planComparison, setPlanComparison] =
    useState<TrainingPlanComparisonResponse | null>(null);
  const [selectedPlanStatus, setSelectedPlanStatus] =
    useState<PlansStatus>("idle");
  const [selectedPlanErrorMessage, setSelectedPlanErrorMessage] =
    useState<string>("");
  const [selectedPlanReloadNonce, setSelectedPlanReloadNonce] =
    useState<number>(0);

  useEffect(() => {
    if (
      typeof window === "undefined" ||
      typeof window.matchMedia !== "function"
    ) {
      return undefined;
    }

    const mediaQuery = window.matchMedia("(max-width: 1180px)");

    /**
     * Apply the responsive shell mode for the current viewport.
     *
     * Parameters:
     *   matchesCompactLayout: Whether the compact layout breakpoint is active.
     *
     * Returns:
     *   void
     *
     * Raises:
     *   This helper does not raise errors directly.
     */
    function applyLayout(matchesCompactLayout: boolean) {
      setIsCompactLayout(matchesCompactLayout);
      setSidebarVisible(!matchesCompactLayout);
    }

    applyLayout(mediaQuery.matches);

    /**
     * Keep the portal shell aligned with media-query changes.
     *
     * Parameters:
     *   event: Browser media-query change payload.
     *
     * Returns:
     *   void
     *
     * Raises:
     *   This helper does not raise errors directly.
     */
    function handleMediaQueryChange(event: MediaQueryListEvent) {
      applyLayout(event.matches);
    }

    mediaQuery.addEventListener("change", handleMediaQueryChange);
    return () => mediaQuery.removeEventListener("change", handleMediaQueryChange);
  }, []);

  useEffect(() => {
    let cancelled = false;

    async function loadPortalData() {
      setStatus("loading");
      setErrorMessage("");

      try {
        const nextData = await getBootstrap(
          selectedDate,
          historyDays,
          trendDays,
          accessToken,
        );
        if (cancelled) {
          return;
        }

        setPortalData(nextData);
        setStatus("ready");
      } catch (error) {
        if (cancelled) {
          return;
        }

        const maybeStatus =
          typeof error === "object" && error !== null
            ? Reflect.get(error, "status")
            : undefined;
        const message =
          error instanceof Error
            ? error.message
            : "Unable to load the APEX portal.";

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

  useEffect(() => {
    setProductsData(null);
    setProductsStatus("idle");
    setProductsErrorMessage("");
    setProductsReloadNonce(0);
    setPlansData(null);
    setPlansStatus("idle");
    setPlansErrorMessage("");
    setPlansReloadNonce(0);
    setSelectedPlanId(null);
    setPlanDetail(null);
    setPlanComparison(null);
    setSelectedPlanStatus("idle");
    setSelectedPlanErrorMessage("");
    setSelectedPlanReloadNonce(0);
  }, [accessToken]);

  useEffect(() => {
    if (activeView !== "products") {
      return;
    }

    if (productsData !== null) {
      return;
    }

    let cancelled = false;

    async function loadProducts() {
      setProductsStatus("loading");
      setProductsErrorMessage("");

      try {
        const nextProducts = await getProducts(accessToken);
        if (cancelled) {
          return;
        }

        setProductsData(nextProducts);
        setProductsStatus("ready");
      } catch (error) {
        if (cancelled) {
          return;
        }

        const maybeStatus =
          typeof error === "object" && error !== null
            ? Reflect.get(error, "status")
            : undefined;
        const message =
          error instanceof Error
            ? error.message
            : "Unable to load the food products.";

        if (maybeStatus === 401) {
          setProductsData(null);
          setProductsStatus("idle");
          setStatus("unlock");
          setErrorMessage(message);
          return;
        }

        setProductsData(null);
        setProductsStatus("error");
        setProductsErrorMessage(message);
      }
    }

    void loadProducts();

    return () => {
      cancelled = true;
    };
  }, [accessToken, activeView, productsData, productsReloadNonce]);

  useEffect(() => {
    if (activeView !== "plans") {
      return;
    }

    if (plansData !== null) {
      return;
    }

    let cancelled = false;

    async function loadPlans() {
      setPlansStatus("loading");
      setPlansErrorMessage("");

      try {
        const nextPlans = await getPlans(accessToken);
        if (cancelled) {
          return;
        }

        setPlansData(nextPlans);
        setPlansStatus("ready");
        setSelectedPlanId((current) => current ?? nextPlans.items[0]?.id ?? null);
      } catch (error) {
        if (cancelled) {
          return;
        }

        const maybeStatus =
          typeof error === "object" && error !== null
            ? Reflect.get(error, "status")
            : undefined;
        const message =
          error instanceof Error
            ? error.message
            : "Unable to load the food and training plans.";

        if (maybeStatus === 401) {
          setPlansData(null);
          setPlansStatus("idle");
          setStatus("unlock");
          setErrorMessage(message);
          return;
        }

        setPlansData(null);
        setPlansStatus("error");
        setPlansErrorMessage(message);
      }
    }

    void loadPlans();

    return () => {
      cancelled = true;
    };
  }, [accessToken, activeView, plansData, plansReloadNonce]);

  useEffect(() => {
    if (activeView !== "plans" || selectedPlanId === null) {
      return;
    }

    const planId = selectedPlanId;
    let cancelled = false;

    async function loadSelectedPlan() {
      setSelectedPlanStatus("loading");
      setSelectedPlanErrorMessage("");

      try {
        const [nextPlan, nextComparison] = await Promise.all([
          getPlan(planId, accessToken),
          getPlanComparison(planId, accessToken),
        ]);
        if (cancelled) {
          return;
        }

        setPlanDetail(nextPlan);
        setPlanComparison(nextComparison);
        setSelectedPlanStatus("ready");
      } catch (error) {
        if (cancelled) {
          return;
        }

        const maybeStatus =
          typeof error === "object" && error !== null
            ? Reflect.get(error, "status")
            : undefined;
        const message =
          error instanceof Error
            ? error.message
            : "Unable to load the selected plan.";

        if (maybeStatus === 401) {
          setPlanDetail(null);
          setPlanComparison(null);
          setSelectedPlanStatus("idle");
          setStatus("unlock");
          setErrorMessage(message);
          return;
        }

        setPlanDetail(null);
        setPlanComparison(null);
        setSelectedPlanStatus("error");
        setSelectedPlanErrorMessage(message);
      }
    }

    void loadSelectedPlan();

    return () => {
      cancelled = true;
    };
  }, [
    accessToken,
    activeView,
    selectedPlanId,
    selectedPlanReloadNonce,
  ]);

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
      activeView={activeView}
      isCompactLayout={isCompactLayout}
      sidebarVisible={sidebarVisible}
      onToggleSidebar={handleToggleSidebar}
      onCloseSidebar={handleCloseSidebar}
      onChangeView={setActiveView}
      onLock={accessToken ? handleLock : undefined}
    >
      {activeView === "today" ? (
        <TodayView
          key={activeDate}
          snapshot={portalData.snapshot}
          selectedDate={activeDate}
          todayDate={todayIsoDate()}
          onSelectDate={setSelectedDate}
          onStepDate={handleStepDate}
        />
      ) : null}

      {activeView === "profile" ? (
        <ProfileView profile={portalData.profile} />
      ) : null}

      {activeView === "products" ? (
        <FoodProductsView
          status={productsStatus}
          errorMessage={productsErrorMessage}
          products={productsData?.items ?? []}
          onRetry={handleRetryProducts}
        />
      ) : null}

      {activeView === "plans" ? (
        <PlansView
          plansStatus={plansStatus}
          plansErrorMessage={plansErrorMessage}
          plans={plansData?.items ?? []}
          selectedPlanId={selectedPlanId}
          selectedPlanStatus={selectedPlanStatus}
          selectedPlanErrorMessage={selectedPlanErrorMessage}
          planDetail={planDetail}
          planComparison={planComparison}
          onSelectPlan={handleSelectPlan}
          onRetryPlans={handleRetryPlans}
          onRetrySelectedPlan={handleRetrySelectedPlan}
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
          dailyMetrics={portalData.trends.daily_metrics}
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

  /**
   * Step the selected day by a single calendar day.
   *
   * Parameters:
   *   direction: Signed day delta to apply.
   *
   * Returns:
   *   void
   *
   * Raises:
   *   This helper does not raise errors directly.
   */
  function handleStepDate(direction: -1 | 1) {
    startTransition(() => {
      const nextDate = shiftIsoDate(activeDate, direction);
      if (direction > 0 && nextDate > todayIsoDate()) {
        return;
      }

      setSelectedDate(nextDate);
    });
  }

  /**
   * Reset the products view so it can fetch again after an error.
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
  function handleRetryProducts() {
    setProductsStatus("idle");
    setProductsErrorMessage("");
    setProductsReloadNonce((current) => current + 1);
  }

  /**
   * Reset the plans view so it can fetch again after an error.
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
  function handleRetryPlans() {
    setPlansData(null);
    setPlansStatus("idle");
    setPlansErrorMessage("");
    setPlansReloadNonce((current) => current + 1);
  }

  /**
   * Reset the selected plan detail and comparison fetch after an error.
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
  function handleRetrySelectedPlan() {
    setPlanDetail(null);
    setPlanComparison(null);
    setSelectedPlanStatus("idle");
    setSelectedPlanErrorMessage("");
    setSelectedPlanReloadNonce((current) => current + 1);
  }

  /**
   * Select one plan from the plans list.
   *
   * Parameters:
   *   planId: Plan identifier selected by the user.
   *
   * Returns:
   *   void
   *
   * Raises:
   *   This helper does not raise errors directly.
   */
  function handleSelectPlan(planId: number) {
    if (planId === selectedPlanId) {
      return;
    }

    setSelectedPlanId(planId);
    setPlanDetail(null);
    setPlanComparison(null);
    setSelectedPlanStatus("idle");
    setSelectedPlanErrorMessage("");
  }

  /**
   * Toggle the mobile sidebar drawer.
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
  function handleToggleSidebar() {
    setSidebarVisible((current) => !current);
  }

  /**
   * Close the mobile sidebar drawer.
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
  function handleCloseSidebar() {
    if (isCompactLayout) {
      setSidebarVisible(false);
    }
  }
}

/**
 * Read whether the compact responsive layout should be active.
 *
 * Parameters:
 *   None.
 *
 * Returns:
 *   boolean: `true` when the viewport matches the compact breakpoint.
 *
 * Raises:
 *   This helper does not raise errors directly.
 */
function readCompactLayoutPreference(): boolean {
  if (
    typeof window === "undefined" ||
    typeof window.matchMedia !== "function"
  ) {
    return false;
  }

  return window.matchMedia("(max-width: 1180px)").matches;
}

/**
 * Read the default sidebar visibility for the current viewport size.
 *
 * Parameters:
 *   None.
 *
 * Returns:
 *   boolean: `true` for desktop layouts, `false` for compact layouts.
 *
 * Raises:
 *   This helper does not raise errors directly.
 */
function readDefaultSidebarVisibility(): boolean {
  return !readCompactLayoutPreference();
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
 *   todayDate: Current browser-local calendar day.
 *   onSelectDate: Callback used when the user changes the date directly.
 *   onStepDate: Callback used when the user moves by a single day.
 *
 * Returns:
 *   JSX.Element: Day review section with progress, meals, and activities.
 *
 * Raises:
 *   This component does not raise errors directly.
 */
function TodayView({
  snapshot,
  selectedDate,
  todayDate,
  onSelectDate,
  onStepDate,
}: {
  snapshot: DailySnapshot;
  selectedDate: string;
  todayDate: string;
  onSelectDate: (value: string) => void;
  onStepDate: (direction: -1 | 1) => void;
}) {
  const summary = snapshot.summary;
  const [openMealIds, setOpenMealIds] = useState<string[]>([]);
  const nextDayDisabled = selectedDate >= todayDate;

  return (
    <section className="portal-section">
      <div className="section-header-row">
        <div>
          <p className="section-kicker">Today</p>
          <h2>{formatLongDate(snapshot.date)}</h2>
          <p className="section-copy">
            Review daily target progress first, then expand meals and activities
            only when you need more detail.
          </p>
        </div>

        <DateNavigator
          selectedDate={selectedDate}
          nextDisabled={nextDayDisabled}
          onSelectDate={onSelectDate}
          onStepDate={onStepDate}
        />
      </div>

      <div className="progress-grid">
        <ProgressPanel
          title="Food calories"
          tone="food"
          current={summary.actual_food_calories}
          target={summary.target_food_calories}
          remainder={summary.remaining_food_calories}
          unit="kcal"
        />
        <ProgressPanel
          title="Protein"
          tone="protein"
          current={summary.actual_protein_g}
          target={summary.target_protein_g}
          remainder={summary.remaining_protein_g}
          unit="g"
        />
        <ProgressPanel
          title="Carbs"
          tone="carbs"
          current={summary.actual_carbs_g}
          target={summary.target_carbs_g}
          remainder={summary.remaining_carbs_g}
          unit="g"
        />
        <ProgressPanel
          title="Fat"
          tone="fat"
          current={summary.actual_fat_g}
          target={summary.target_fat_g}
          remainder={summary.remaining_fat_g}
          unit="g"
        />
      </div>

      <div className="panel">
        <div className="panel-header">
          <h3>Meals</h3>
          <span>{summary.meal_items_count} ingredients logged</span>
        </div>

        {snapshot.meals.length === 0 ? (
          <EmptyPanel message="No meals logged for this day yet." />
        ) : (
          <div className="meal-list">
            {snapshot.meals.map((meal) => (
              <MealAccordionCard
                key={meal.id}
                meal={meal}
                isOpen={openMealIds.includes(meal.id)}
                onToggle={() => setOpenMealIds((current) => toggleMeal(current, meal.id))}
              />
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
              <ActivityCard key={activity.id} activity={activity} />
            ))}
          </div>
        )}
      </div>
    </section>
  );
}

/**
 * Render the athlete profile page.
 *
 * Parameters:
 *   profile: Athlete context returned by the bootstrap payload.
 *
 * Returns:
 *   JSX.Element: Read-only profile summary and markdown sections.
 *
 * Raises:
 *   This component does not raise errors directly.
 */
function ProfileView({ profile }: { profile: PortalProfile }) {
  return (
    <section className="portal-section">
      <div className="section-header-row">
        <div>
          <p className="section-kicker">Profile</p>
          <h2>{profile.athlete_name}</h2>
          <p className="section-copy">
            Read-only athlete context sourced from the APEX database.
          </p>
        </div>
      </div>

      <div className="profile-summary-grid">
        <ProfileStat
          label="Weight"
          value={
            profile.weight_kg === null
              ? "Not set"
              : `${profile.weight_kg.toFixed(1)} kg`
          }
        />
        <ProfileStat
          label="Height"
          value={
            profile.height_cm === null
              ? "Not set"
              : `${profile.height_cm.toFixed(0)} cm`
          }
        />
        <ProfileStat
          label="FTP"
          value={
            profile.ftp_watts === null ? "Not set" : `${profile.ftp_watts} W`
          }
        />
      </div>

      <ProfileDocumentSection
        title="Profile overview"
        markdown={profile.profile_markdown}
      />
      <ProfileDocumentSection
        title="Training goals"
        markdown={profile.training_goals_markdown}
      />
      <ProfileDocumentSection
        title="Diet goals"
        markdown={profile.diet_goals_markdown}
      />
    </section>
  );
}

/**
 * Render the reusable food products page.
 *
 * Parameters:
 *   status: Current async status for the products fetch.
 *   errorMessage: Error shown when the fetch fails.
 *   products: Cached product rows.
 *   onRetry: Callback used to retry after an error.
 *
 * Returns:
 *   JSX.Element: Food product table or supporting empty/loading states.
 *
 * Raises:
 *   This component does not raise errors directly.
 */
function FoodProductsView({
  status,
  errorMessage,
  products,
  onRetry,
}: {
  status: ProductsStatus;
  errorMessage: string;
  products: FoodProduct[];
  onRetry: () => void;
}) {
  const [searchTerm, setSearchTerm] = useState<string>("");
  const [sortKey, setSortKey] = useState<ProductsSortKey>("name");
  const [sortDirection, setSortDirection] = useState<SortDirection>("asc");
  const deferredSearchTerm = useDeferredValue(searchTerm.trim().toLowerCase());
  const visibleProducts = sortProducts(
    products.filter((product) =>
      matchesProductSearch(product, deferredSearchTerm),
    ),
    sortKey,
    sortDirection,
  );

  return (
    <section className="portal-section">
      <div className="section-header-row">
        <div>
          <p className="section-kicker">Food products</p>
          <h2>Reusable catalog</h2>
          <p className="section-copy">
            Review the saved food products that power faster meal logging in
            APEX.
          </p>
        </div>
      </div>

      <div className="panel">
        {status === "loading" || status === "idle" ? (
          <EmptyPanel message="Loading food products..." />
        ) : null}

        {status === "error" ? (
          <div className="inline-error">
            <p>{errorMessage}</p>
            <button type="button" onClick={onRetry}>
              Retry
            </button>
          </div>
        ) : null}

        {status === "ready" && products.length === 0 ? (
          <EmptyPanel message="No reusable food products were found for this athlete." />
        ) : null}

        {status === "ready" && products.length > 0 ? (
          <div className="products-catalog">
            <div className="products-toolbar">
              <label className="products-toolbar-field products-search-field">
                <span>Search</span>
                <input
                  type="search"
                  value={searchTerm}
                  placeholder="Search by food or brand"
                  onChange={(event) => setSearchTerm(event.target.value)}
                />
              </label>

              <label className="products-toolbar-field">
                <span>Sort</span>
                <select
                  value={sortKey}
                  onChange={(event) =>
                    setSortKey(event.target.value as ProductsSortKey)
                  }
                >
                  <option value="name">Name</option>
                  <option value="default_serving_g">Default serving</option>
                  <option value="calories_per_100g">Calories / 100g</option>
                  <option value="carbs_g_per_100g">Carbs</option>
                  <option value="protein_g_per_100g">Protein</option>
                  <option value="fat_g_per_100g">Fat</option>
                  <option value="usage_count">Times used</option>
                </select>
              </label>

              <label className="products-toolbar-field">
                <span>Direction</span>
                <select
                  value={sortDirection}
                  onChange={(event) =>
                    setSortDirection(event.target.value as SortDirection)
                  }
                >
                  <option value="asc">Ascending</option>
                  <option value="desc">Descending</option>
                </select>
              </label>
            </div>

            <div className="products-toolbar-caption">
              <span>
                {visibleProducts.length} of {products.length} foods shown
              </span>
            </div>

            {visibleProducts.length === 0 ? (
              <EmptyPanel message="No food products match the current search." />
            ) : (
              <div className="products-table-wrap">
                <table className="products-table">
                  <thead>
                    <tr>
                      <th>
                        <ProductsTableHeading label="Name" />
                      </th>
                      <th>
                        <ProductsTableHeading label="Default serving" />
                      </th>
                      <th>
                        <ProductsTableHeading label="Calories" unit="/100g" />
                      </th>
                      <th>
                        <ProductsTableHeading label="Carbs" unit="/100g" />
                      </th>
                      <th>
                        <ProductsTableHeading label="Protein" unit="/100g" />
                      </th>
                      <th>
                        <ProductsTableHeading label="Fat" unit="/100g" />
                      </th>
                      <th>
                        <ProductsTableHeading label="Used" unit="times" />
                      </th>
                    </tr>
                  </thead>
                  <tbody>
                    {visibleProducts.map((product) => (
                      <tr key={product.id}>
                        <td>{product.name}</td>
                        <td>{formatTableValue(product.default_serving_g, "g")}</td>
                        <td>{formatTableValue(product.calories_per_100g, "kcal")}</td>
                        <td>{formatTableValue(product.carbs_g_per_100g, "g")}</td>
                        <td>{formatTableValue(product.protein_g_per_100g, "g")}</td>
                        <td>{formatTableValue(product.fat_g_per_100g, "g")}</td>
                        <td>{formatUsageCount(product.usage_count)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        ) : null}
      </div>
    </section>
  );
}

/**
 * Render the read-only food and training plans page.
 *
 * Parameters:
 *   plansStatus: Async status for the plan list fetch.
 *   plansErrorMessage: Error shown when plan list loading fails.
 *   plans: Cached plan header rows.
 *   selectedPlanId: Currently selected plan id.
 *   selectedPlanStatus: Async status for selected plan detail/comparison.
 *   selectedPlanErrorMessage: Error shown when selected plan loading fails.
 *   planDetail: Current selected plan detail.
 *   planComparison: Current selected plan comparison.
 *   onSelectPlan: Callback used when the user selects a plan.
 *   onRetryPlans: Callback used to retry the plan list.
 *   onRetrySelectedPlan: Callback used to retry selected plan data.
 *
 * Returns:
 *   JSX.Element: Plans list, calendar/detail, and comparison surface.
 *
 * Raises:
 *   This component does not raise errors directly.
 */
function PlansView({
  plansStatus,
  plansErrorMessage,
  plans,
  selectedPlanId,
  selectedPlanStatus,
  selectedPlanErrorMessage,
  planDetail,
  planComparison,
  onSelectPlan,
  onRetryPlans,
  onRetrySelectedPlan,
}: {
  plansStatus: PlansStatus;
  plansErrorMessage: string;
  plans: TrainingPlansResponse["items"];
  selectedPlanId: number | null;
  selectedPlanStatus: PlansStatus;
  selectedPlanErrorMessage: string;
  planDetail: TrainingPlanDetail | null;
  planComparison: TrainingPlanComparisonResponse | null;
  onSelectPlan: (planId: number) => void;
  onRetryPlans: () => void;
  onRetrySelectedPlan: () => void;
}) {
  const [activePanel, setActivePanel] = useState<PlanPanel>("calendar");

  return (
    <section className="portal-section">
      <div className="section-header-row">
        <div>
          <p className="section-kicker">Plans</p>
          <h2>Food and training plans</h2>
          <p className="section-copy">
            Review planned training, nutrition targets, fueling guidance, and
            actual outcomes from the APEX planning layer.
          </p>
        </div>
      </div>

      {plansStatus === "loading" || plansStatus === "idle" ? (
        <EmptyPanel message="Loading food and training plans..." />
      ) : null}

      {plansStatus === "error" ? (
        <div className="inline-error">
          <p>{plansErrorMessage}</p>
          <button type="button" onClick={onRetryPlans}>
            Retry
          </button>
        </div>
      ) : null}

      {plansStatus === "ready" && plans.length === 0 ? (
        <EmptyPanel message="No food and training plans were found for this athlete." />
      ) : null}

      {plansStatus === "ready" && plans.length > 0 ? (
        <div className="plans-layout">
          <aside className="plans-list-panel" aria-label="Training plans">
            <div className="plans-list-header">
              <h3>Plan list</h3>
              <span>{plans.length} stored</span>
            </div>

            <div className="plans-list">
              {plans.map((plan) => (
                <button
                  key={plan.id}
                  type="button"
                  className={`plan-list-item${
                    plan.id === selectedPlanId ? " active" : ""
                  }`}
                  onClick={() => onSelectPlan(plan.id)}
                >
                  <span className="plan-list-item-topline">
                    <strong>{plan.title}</strong>
                    <PlanStatusBadge status={plan.status} />
                  </span>
                  <span>{formatPlanDateRange(plan.start_date, plan.end_date)}</span>
                  <span>
                    {plan.days_count} {plan.days_count === 1 ? "day" : "days"}
                  </span>
                </button>
              ))}
            </div>
          </aside>

          <div className="plans-detail-stack">
            {selectedPlanStatus === "loading" ||
            selectedPlanStatus === "idle" ? (
              <EmptyPanel message="Loading selected plan..." />
            ) : null}

            {selectedPlanStatus === "error" ? (
              <div className="inline-error">
                <p>{selectedPlanErrorMessage}</p>
                <button type="button" onClick={onRetrySelectedPlan}>
                  Retry
                </button>
              </div>
            ) : null}

            {selectedPlanStatus === "ready" &&
            planDetail !== null &&
            planComparison !== null ? (
              <>
                <PlanOverview plan={planDetail} />

                <div className="plan-panel-toggle" role="tablist">
                  <button
                    type="button"
                    className={activePanel === "calendar" ? "active" : ""}
                    onClick={() => setActivePanel("calendar")}
                  >
                    Calendar
                  </button>
                  <button
                    type="button"
                    className={activePanel === "comparison" ? "active" : ""}
                    onClick={() => setActivePanel("comparison")}
                  >
                    Comparison
                  </button>
                </div>

                {activePanel === "calendar" ? (
                  <PlanCalendar plan={planDetail} />
                ) : (
                  <PlanComparisonPanel comparison={planComparison} />
                )}
              </>
            ) : null}
          </div>
        </div>
      ) : null}
    </section>
  );
}

/**
 * Render the selected plan header and explanatory markdown sections.
 *
 * Parameters:
 *   plan: Selected plan detail payload.
 *
 * Returns:
 *   JSX.Element: Plan summary and markdown context.
 *
 * Raises:
 *   This component does not raise errors directly.
 */
function PlanOverview({ plan }: { plan: TrainingPlanDetail }) {
  return (
    <>
      <div className="plan-overview-panel">
        <div>
          <div className="plan-title-row">
            <h3>{plan.title}</h3>
            <PlanStatusBadge status={plan.status} />
          </div>
          <p>{formatPlanDateRange(plan.start_date, plan.end_date)}</p>
        </div>

        <div className="plan-overview-stats">
          <ProfileStat
            label="Planned days"
            value={String(plan.days.length || plan.days_count)}
          />
          <ProfileStat
            label="Updated"
            value={formatShortDate(plan.updated_at.slice(0, 10))}
          />
        </div>
      </div>

      <div className="plan-markdown-grid">
        <ProfileDocumentSection title="Goal" markdown={plan.goal_markdown} />
        <ProfileDocumentSection
          title="Rationale"
          markdown={plan.rationale_markdown}
        />
        <ProfileDocumentSection title="Notes" markdown={plan.notes_markdown} />
      </div>
    </>
  );
}

/**
 * Render the selected plan as a 7-column calendar grid.
 *
 * Parameters:
 *   plan: Selected plan detail payload.
 *
 * Returns:
 *   JSX.Element: Calendar grid with one planned day card per date.
 *
 * Raises:
 *   This component does not raise errors directly.
 */
function PlanCalendar({ plan }: { plan: TrainingPlanDetail }) {
  const daysByDate = new Map(plan.days.map((day) => [day.plan_date, day]));
  const calendarCells = getPlanCalendarCells(plan.start_date, plan.end_date);

  return (
    <div className="plan-calendar-panel">
      <div className="panel-header">
        <h3>Plan calendar</h3>
        <span>{plan.days.length} planned rows</span>
      </div>

      <div className="plan-calendar-weekdays" aria-hidden="true">
        {["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"].map((dayLabel) => (
          <span key={dayLabel}>{dayLabel}</span>
        ))}
      </div>

      <div className="plan-calendar-grid">
        {calendarCells.map((cellDate, index) => {
          if (cellDate === null) {
            return <div key={`blank-${index}`} className="plan-calendar-empty" />;
          }

          const planDay = daysByDate.get(cellDate);
          return (
            <div key={cellDate} className="plan-calendar-cell">
              <span className="plan-calendar-date">{formatShortDate(cellDate)}</span>
              {planDay ? (
                <PlanDayCard day={planDay} />
              ) : (
                <EmptyPanel message="No planned row for this date." />
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

/**
 * Render one planned day as an expandable calendar card.
 *
 * Parameters:
 *   day: Plan-day payload.
 *
 * Returns:
 *   JSX.Element: Planned day card with training, targets, and guidance.
 *
 * Raises:
 *   This component does not raise errors directly.
 */
function PlanDayCard({ day }: { day: TrainingPlanDay }) {
  return (
    <details className={`plan-day-card ${day.day_type}`}>
      <summary>
        <span className="plan-day-card-kicker">
          {day.day_type}
          {day.primary_sport_type ? ` / ${day.primary_sport_type}` : ""}
        </span>
        <strong>{day.title || "Planned day"}</strong>
        {day.training_summary ? <p>{day.training_summary}</p> : null}
        <div className="plan-day-card-stats">
          <span>{formatDuration(day.planned_duration_seconds)}</span>
          <span>{formatDistance(day.planned_distance_meters)}</span>
          <span>{formatCalories(day.target_food_calories)}</span>
        </div>
      </summary>

      <div className="plan-day-card-body">
        <div className="plan-target-grid">
          <SummaryChip
            tone="food"
            label="Food"
            value={formatCompactAmount(day.target_food_calories, "kcal")}
          />
          <SummaryChip
            tone="exercise"
            label="Exercise"
            value={formatCompactAmount(day.target_exercise_calories, "kcal")}
          />
          <SummaryChip
            tone="protein"
            label="Protein"
            value={formatCompactAmount(day.target_protein_g, "g")}
          />
          <SummaryChip
            tone="carbs"
            label="Carbs"
            value={formatCompactAmount(day.target_carbs_g, "g")}
          />
          <SummaryChip
            tone="fat"
            label="Fat"
            value={formatCompactAmount(day.target_fat_g, "g")}
          />
          {day.planned_training_load !== null ? (
            <SummaryChip
              tone="load"
              label="Load"
              value={Math.round(day.planned_training_load).toLocaleString()}
            />
          ) : null}
        </div>

        <PlanStructuredSection
          title="Training sessions"
          items={day.training_sessions}
        />
        <PlanJsonObject title="Fueling" value={day.fueling_plan} />
        <PlanJsonObject title="Menu" value={day.menu_plan} />

        {day.notes_markdown ? (
          <div className="plan-day-notes">
            <MarkdownContent markdown={day.notes_markdown} />
          </div>
        ) : null}
      </div>
    </details>
  );
}

/**
 * Render structured JSON list items from a plan day.
 *
 * Parameters:
 *   title: Section title.
 *   items: Structured list of JSON object entries.
 *
 * Returns:
 *   JSX.Element | null: Rendered structured section when entries exist.
 *
 * Raises:
 *   This component does not raise errors directly.
 */
function PlanStructuredSection({
  title,
  items,
}: {
  title: string;
  items: Array<Record<string, unknown>>;
}) {
  if (items.length === 0) {
    return null;
  }

  return (
    <div className="plan-structured-section">
      <h4>{title}</h4>
      {items.map((item, index) => (
        <dl key={index}>
          <dt>Session {index + 1}</dt>
          <dd>{formatJsonObject(item)}</dd>
        </dl>
      ))}
    </div>
  );
}

/**
 * Render one object-shaped plan guidance block.
 *
 * Parameters:
 *   title: Section title.
 *   value: Object-shaped JSON value to render.
 *
 * Returns:
 *   JSX.Element | null: Description list when the object has entries.
 *
 * Raises:
 *   This component does not raise errors directly.
 */
function PlanJsonObject({
  title,
  value,
}: {
  title: string;
  value: Record<string, unknown>;
}) {
  const entries = Object.entries(value).filter(([, entryValue]) =>
    hasDisplayValue(entryValue),
  );
  if (entries.length === 0) {
    return null;
  }

  return (
    <div className="plan-structured-section">
      <h4>{title}</h4>
      <dl>
        {entries.map(([key, entryValue]) => (
          <div key={key}>
            <dt>{formatMetricTypeLabel(key)}</dt>
            <dd>{formatJsonValue(entryValue)}</dd>
          </div>
        ))}
      </dl>
    </div>
  );
}

/**
 * Render planned-vs-actual comparison totals and day rows.
 *
 * Parameters:
 *   comparison: Selected plan comparison payload.
 *
 * Returns:
 *   JSX.Element: Comparison panel with totals and per-day rows.
 *
 * Raises:
 *   This component does not raise errors directly.
 */
function PlanComparisonPanel({
  comparison,
}: {
  comparison: TrainingPlanComparisonResponse;
}) {
  const totals = comparison.totals;

  return (
    <div className="plan-comparison-panel">
      <div className="metric-grid">
        <MetricCard
          title="Food delta"
          primary={formatSignedValue(totals.food_calories_delta, "kcal")}
          secondary={`${formatCalories(totals.actual_food_calories)} actual / ${formatCalories(
            totals.planned_food_calories,
          )} planned`}
        />
        <MetricCard
          title="Exercise delta"
          primary={formatSignedValue(totals.exercise_calories_delta, "kcal")}
          secondary={`${formatCalories(
            totals.actual_exercise_calories,
          )} actual / ${formatCalories(totals.planned_exercise_calories)} planned`}
        />
        <MetricCard
          title="Macro delta"
          primary={formatSignedValue(totals.carbs_g_delta, "g carbs")}
          secondary={`${formatSignedValue(
            totals.protein_g_delta,
            "g protein",
          )}, ${formatSignedValue(totals.fat_g_delta, "g fat")}`}
        />
        <MetricCard
          title="Compared days"
          primary={String(totals.days_count)}
          secondary="Missing actuals are shown as missing data"
        />
      </div>

      <div className="panel">
        <div className="panel-header">
          <h3>Planned vs actual</h3>
          <span>{comparison.days_count} days compared</span>
        </div>

        <div className="plan-comparison-list">
          {comparison.days.map((day) => (
            <PlanComparisonRow key={day.plan_date} day={day} />
          ))}
        </div>
      </div>
    </div>
  );
}

/**
 * Render one planned-vs-actual day row.
 *
 * Parameters:
 *   day: One comparison day.
 *
 * Returns:
 *   JSX.Element: Day-level comparison row.
 *
 * Raises:
 *   This component does not raise errors directly.
 */
function PlanComparisonRow({
  day,
}: {
  day: TrainingPlanComparisonResponse["days"][number];
}) {
  const hasActuals =
    day.actual.meals_count > 0 || day.actual.activities_count > 0;

  return (
    <article className={`plan-comparison-row${hasActuals ? "" : " missing"}`}>
      <div className="plan-comparison-row-header">
        <div>
          <strong>{formatLongDate(day.plan_date)}</strong>
          <span>{day.planned.title || day.planned.day_type}</span>
        </div>
        <span>{hasActuals ? "Actuals logged" : "Missing actuals"}</span>
      </div>

      <div className="plan-comparison-metrics">
        <SummaryChip
          tone="food"
          label="Food"
          value={`${formatCompactAmount(day.actual.actual_food_calories, "kcal")} / ${formatCompactAmount(
            day.planned.target_food_calories,
            "kcal",
          )}`}
        />
        <SummaryChip
          tone="exercise"
          label="Exercise"
          value={`${formatCompactAmount(
            day.actual.actual_exercise_calories,
            "kcal",
          )} / ${formatCompactAmount(day.planned.target_exercise_calories, "kcal")}`}
        />
        <SummaryChip
          tone="protein"
          label="Protein"
          value={`${formatCompactAmount(day.actual.actual_protein_g, "g")} / ${formatCompactAmount(
            day.planned.target_protein_g,
            "g",
          )}`}
        />
        <SummaryChip
          tone="carbs"
          label="Carbs"
          value={`${formatCompactAmount(day.actual.actual_carbs_g, "g")} / ${formatCompactAmount(
            day.planned.target_carbs_g,
            "g",
          )}`}
        />
        <SummaryChip
          tone="fat"
          label="Fat"
          value={`${formatCompactAmount(day.actual.actual_fat_g, "g")} / ${formatCompactAmount(
            day.planned.target_fat_g,
            "g",
          )}`}
        />
      </div>

      <div className="plan-comparison-deltas">
        <span>Food {formatSignedValue(day.deltas.food_calories, "kcal")}</span>
        <span>
          Exercise {formatSignedValue(day.deltas.exercise_calories, "kcal")}
        </span>
        <span>Protein {formatSignedValue(day.deltas.protein_g, "g")}</span>
        <span>Carbs {formatSignedValue(day.deltas.carbs_g, "g")}</span>
        <span>Fat {formatSignedValue(day.deltas.fat_g, "g")}</span>
      </div>

      <div className="adherence-grid">
        <AdherenceBar
          label="Food adherence"
          value={day.adherence.food_calories_percent}
        />
        <AdherenceBar
          label="Exercise adherence"
          value={day.adherence.exercise_calories_percent}
        />
        <AdherenceBar
          label="Macro average"
          value={day.adherence.macro_average_percent}
        />
      </div>

      <div className="plan-comparison-context">
        <span>{day.actual.meals_count} meals</span>
        <span>{day.actual.activities_count} activities</span>
        {day.daily_metrics.map((metric) => (
          <span key={`${metric.metric_type}-${metric.metric_date}`}>
            {formatMetricTypeLabel(metric.metric_type)}{" "}
            {formatDailyMetricValue(metric.metric_type, metric.value)}
          </span>
        ))}
      </div>
    </article>
  );
}

/**
 * Render one adherence bar.
 *
 * Parameters:
 *   label: Bar label.
 *   value: Optional adherence percentage.
 *
 * Returns:
 *   JSX.Element: Small progress bar with numeric label.
 *
 * Raises:
 *   This component does not raise errors directly.
 */
function AdherenceBar({
  label,
  value,
}: {
  label: string;
  value: number | null;
}) {
  return (
    <div className="adherence-bar">
      <div>
        <span>{label}</span>
        <strong>{value === null ? "No target" : `${Math.round(value)}%`}</strong>
      </div>
      <div className="adherence-track" aria-hidden="true">
        <span style={{ width: `${value ?? 0}%` }} />
      </div>
    </div>
  );
}

/**
 * Render one status badge for plan lifecycle state.
 *
 * Parameters:
 *   status: Raw lifecycle status.
 *
 * Returns:
 *   JSX.Element: Styled plan status label.
 *
 * Raises:
 *   This component does not raise errors directly.
 */
function PlanStatusBadge({ status }: { status: string }) {
  return (
    <span className={`plan-status-badge ${status}`}>
      {formatMetricTypeLabel(status)}
    </span>
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
                <div className="history-row-header">
                  <div className="history-row-primary">
                    <strong>{formatLongDate(day.date)}</strong>
                    <span>{formatTrackedCounts(day.meals_count, day.activities_count)}</span>
                  </div>
                  <span className="history-row-date-badge">
                    {day.date === selectedDate ? "Open day" : "Review day"}
                  </span>
                </div>

                <div className="history-row-metrics">
                  <SummaryChip
                    tone="food"
                    label="Food"
                    value={formatCurrentTargetValue(
                      day.actual_food_calories,
                      day.target_food_calories,
                      "kcal",
                    )}
                  />
                  <SummaryChip
                    tone="exercise"
                    label="Exercise"
                    value={formatCompactAmount(day.actual_exercise_calories, "kcal")}
                  />
                  <SummaryChip
                    tone="protein"
                    label="Protein"
                    value={formatCurrentTargetValue(
                      day.actual_protein_g,
                      day.target_protein_g,
                      "g",
                    )}
                  />
                  <SummaryChip
                    tone="carbs"
                    label="Carbs"
                    value={formatCurrentTargetValue(
                      day.actual_carbs_g,
                      day.target_carbs_g,
                      "g",
                    )}
                  />
                  <SummaryChip
                    tone="fat"
                    label="Fat"
                    value={formatCurrentTargetValue(
                      day.actual_fat_g,
                      day.target_fat_g,
                      "g",
                    )}
                  />
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
 *   dailyMetrics: Dynamic metric series grouped by metric type.
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
  dailyMetrics,
  summary,
  onChangeMetric,
  onChangeWindow,
}: {
  trendDays: number;
  trendMetric: TrendMetric;
  days: HistoryDay[];
  dailyMetrics: DailyMetricSeries[];
  summary: BootstrapResponse["trends"]["summary"];
  onChangeMetric: (value: TrendMetric) => void;
  onChangeWindow: (value: number) => void;
}) {
  const selectedDailyMetric = getSelectedDailyMetric(trendMetric, dailyMetrics);
  const activeMetric =
    selectedDailyMetric || !isDailyTrendMetric(trendMetric)
      ? trendMetric
      : "food";
  const dailyMetricIndex = selectedDailyMetric
    ? dailyMetrics.findIndex(
        (dailyMetric) =>
          dailyMetric.metric_type === selectedDailyMetric.metric_type,
      )
    : -1;
  const metricMeta = selectedDailyMetric
    ? getDailyMetricMeta(selectedDailyMetric.metric_type, dailyMetricIndex)
    : getTrendMetricMeta(activeMetric as BuiltInTrendMetric);
  const chartValues = selectedDailyMetric
    ? selectedDailyMetric.points.map((point) => point.value)
    : days.map((day) => metricMeta.pickValue(day));
  const targetValues = selectedDailyMetric
    ? []
    : days.map((day) => metricMeta.pickTarget(day));
  const chartLabels = selectedDailyMetric
    ? selectedDailyMetric.points.map((point) => formatShortDate(point.date))
    : days.map((day) => formatShortDate(day.date));

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
        {BUILT_IN_TREND_METRICS.map(
          (metric) => (
            <button
              key={metric}
              type="button"
              className={`trend-toggle${metric === activeMetric ? " active" : ""}`}
              onClick={() => onChangeMetric(metric)}
            >
              {getTrendMetricMeta(metric).label}
            </button>
          ),
        )}
        {dailyMetrics.map((dailyMetric) => {
          const dailyMetricKey = getDailyMetricKey(dailyMetric.metric_type);
          return (
            <button
              key={dailyMetricKey}
              type="button"
              className={`trend-toggle${
                dailyMetricKey === activeMetric ? " active" : ""
              }`}
              onClick={() => onChangeMetric(dailyMetricKey)}
            >
              {formatMetricTypeLabel(dailyMetric.metric_type)}
            </button>
          );
        })}
      </div>

      <div className="panel">
        <div className="panel-header">
          <h3>{metricMeta.label}</h3>
          <span>{metricMeta.subtitle}</span>
        </div>
        <TrendChart
          values={chartValues}
          comparisonValues={targetValues}
          labels={chartLabels}
          accent={metricMeta.color}
          comparisonAccent={metricMeta.targetColor}
          valueLabel={metricMeta.valueLabel}
          comparisonLabel={metricMeta.targetLabel}
          formatValue={metricMeta.formatValue}
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
 * Render the date navigator used above the daily review.
 *
 * Parameters:
 *   selectedDate: Business date currently displayed.
 *   nextDisabled: Whether the next-day button should be disabled.
 *   onSelectDate: Callback used when the user picks a date directly.
 *   onStepDate: Callback used when the user moves by one day.
 *
 * Returns:
 *   JSX.Element: Arrow controls flanking the date field.
 *
 * Raises:
 *   This component does not raise errors directly.
 */
function DateNavigator({
  selectedDate,
  nextDisabled,
  onSelectDate,
  onStepDate,
}: {
  selectedDate: string;
  nextDisabled: boolean;
  onSelectDate: (value: string) => void;
  onStepDate: (direction: -1 | 1) => void;
}) {
  return (
    <div className="date-picker date-navigator">
      <div className="date-navigator-row">
        <button
          type="button"
          className="date-step-button"
          aria-label="Previous day"
          onClick={() => onStepDate(-1)}
        >
          ←
        </button>

        <div className="date-input-shell">
          <input
            type="date"
            value={selectedDate}
            onChange={(event) => onSelectDate(event.target.value)}
          />
        </div>

        <button
          type="button"
          className="date-step-button"
          aria-label="Next day"
          disabled={nextDisabled}
          onClick={() => onStepDate(1)}
        >
          →
        </button>
      </div>
    </div>
  );
}

/**
 * Render one meal as a collapsible details block.
 *
 * Parameters:
 *   meal: Meal and ingredient data for the selected day.
 *   isOpen: Whether the meal is currently expanded.
 *   onToggle: Callback used when the meal opens or closes.
 *
 * Returns:
 *   JSX.Element: Accordion-style meal card with ingredient details.
 *
 * Raises:
 *   This component does not raise errors directly.
 */
function MealAccordionCard({
  meal,
  isOpen,
  onToggle,
}: {
  meal: DailySnapshot["meals"][number];
  isOpen: boolean;
  onToggle: () => void;
}) {
  return (
    <details className="meal-card" open={isOpen}>
      <summary
        className="meal-summary"
        onClick={(event) => {
          event.preventDefault();
          onToggle();
        }}
      >
        <div className="meal-summary-copy">
          <h4>{meal.meal_label}</h4>
        </div>

        <div className="meal-summary-meta">
          <span className="meal-item-count">
            {meal.items.length} {meal.items.length === 1 ? "item" : "items"}
          </span>
          <div className="meal-totals">
            <NutrientBadge
              tone="calories"
              label="Calories"
              value={formatCompactAmount(meal.total_calories, "kcal")}
            />
            <NutrientBadge
              tone="protein"
              label="Protein"
              value={formatCompactAmount(meal.total_protein_g, "g")}
            />
            <NutrientBadge
              tone="carbs"
              label="Carbs"
              value={formatCompactAmount(meal.total_carbs_g, "g")}
            />
            <NutrientBadge
              tone="fat"
              label="Fat"
              value={formatCompactAmount(meal.total_fat_g, "g")}
            />
          </div>
        </div>
      </summary>

      {meal.notes_markdown ? (
        <p className="meal-note">{meal.notes_markdown}</p>
      ) : null}

      <div className="meal-items">
        <div className="meal-items-header">
          <span>Ingredient breakdown</span>
          <span>
            {meal.items.length} {meal.items.length === 1 ? "ingredient" : "ingredients"}
          </span>
        </div>
        {meal.items.map((item) => (
          <MealItemRow key={item.id} item={item} />
        ))}
      </div>
    </details>
  );
}

/**
 * Render one logged activity card.
 *
 * Parameters:
 *   activity: Activity detail for the selected day.
 *
 * Returns:
 *   JSX.Element: Activity card with highlighted summary chips and notes.
 *
 * Raises:
 *   This component does not raise errors directly.
 */
function ActivityCard({
  activity,
}: {
  activity: DailySnapshot["activities"][number];
}) {
  return (
    <article className="activity-card">
      <div className="activity-card-header">
        <div>
          <h4>{activity.title}</h4>
          <p>
            {activity.sport_type ?? "Activity"}
            {activity.external_source ? ` • ${activity.external_source}` : ""}
          </p>
        </div>
      </div>

      <div className="activity-highlights">
        <SummaryChip
          tone="food"
          label="Calories"
          value={
            activity.calories === null
              ? "No calorie data"
              : formatCompactAmount(activity.calories, "kcal")
          }
        />
        {activity.suffer_score !== null ? (
          <SummaryChip
            tone="load"
            label="Training load"
            value={Math.round(activity.suffer_score).toLocaleString()}
          />
        ) : null}
      </div>

      <div className="activity-stats">
        <span>Distance {formatDistance(activity.distance_meters)}</span>
        <span>Time {formatDuration(activity.moving_time_seconds)}</span>
        <span>
          Climb{" "}
          {activity.total_elevation_gain_meters
            ? `${Math.round(activity.total_elevation_gain_meters)} m+`
            : "0 m+"}
        </span>
        <span>
          Avg HR{" "}
          {activity.average_heartrate
            ? `${Math.round(activity.average_heartrate)} bpm`
            : "n/a"}
        </span>
      </div>

      {activity.notes_markdown ? (
        <p className="activity-note">{activity.notes_markdown}</p>
      ) : null}
    </article>
  );
}

/**
 * Render one ingredient row inside an expanded meal.
 *
 * Parameters:
 *   item: Logged meal item with per-serving nutrition values.
 *
 * Returns:
 *   JSX.Element: Ingredient name, grams, and macro badges.
 *
 * Raises:
 *   This component does not raise errors directly.
 */
function MealItemRow({
  item,
}: {
  item: DailySnapshot["meals"][number]["items"][number];
}) {
  return (
    <div className="meal-item-row">
      <div className="meal-item-copy">
        <p className="meal-item-kicker">Ingredient</p>
        <strong>{item.ingredient_name}</strong>
        <span>{Math.round(item.grams)} g</span>
      </div>

      <div className="meal-item-metrics">
        <IngredientMetricPill
          tone="calories"
          label="Calories"
          value={formatCompactAmount(item.calories, "kcal")}
        />
        <IngredientMetricPill
          tone="protein"
          label="Protein"
          value={formatCompactAmount(item.protein_g, "g")}
        />
        <IngredientMetricPill
          tone="carbs"
          label="Carbs"
          value={formatCompactAmount(item.carbs_g, "g")}
        />
        <IngredientMetricPill
          tone="fat"
          label="Fat"
          value={formatCompactAmount(item.fat_g, "g")}
        />
      </div>
    </div>
  );
}

/**
 * Render one reusable nutrient badge for meal summaries and rows.
 *
 * Parameters:
 *   tone: Color treatment used by the badge.
 *   label: Accessible label for the nutrient.
 *   value: Visible formatted nutrient value.
 *
 * Returns:
 *   JSX.Element: Styled nutrient badge.
 *
 * Raises:
 *   This component does not raise errors directly.
 */
function NutrientBadge({
  tone,
  label,
  value,
}: {
  tone: "calories" | "protein" | "carbs" | "fat";
  label: string;
  value: string;
}) {
  return (
    <span className={`nutrient-badge ${tone}`}>
      <em>{label}</em>
      <strong>{value}</strong>
    </span>
  );
}

/**
 * Render a nested ingredient metric pill with a different visual language.
 *
 * Parameters:
 *   tone: Color treatment used by the pill.
 *   label: Visible label for the nutrient.
 *   value: Visible formatted nutrient value.
 *
 * Returns:
 *   JSX.Element: Compact ingredient detail pill.
 *
 * Raises:
 *   This component does not raise errors directly.
 */
function IngredientMetricPill({
  tone,
  label,
  value,
}: {
  tone: "calories" | "protein" | "carbs" | "fat";
  label: string;
  value: string;
}) {
  return (
    <span className={`ingredient-metric-pill ${tone}`}>
      <em>{label}</em>
      <strong>{value}</strong>
    </span>
  );
}

/**
 * Render one compact summary chip for history and activity metadata.
 *
 * Parameters:
 *   tone: Color treatment used by the chip.
 *   label: Visible chip label.
 *   value: Formatted value shown on the right.
 *
 * Returns:
 *   JSX.Element: Styled summary chip.
 *
 * Raises:
 *   This component does not raise errors directly.
 */
function SummaryChip({
  tone,
  label,
  value,
}: {
  tone: "food" | "exercise" | "protein" | "carbs" | "fat" | "load";
  label: string;
  value: string;
}) {
  return (
    <span className={`summary-chip ${tone}`}>
      <em>{label}</em>
      <strong>{value}</strong>
    </span>
  );
}

/**
 * Render one profile document section.
 *
 * Parameters:
 *   title: Section title shown above the markdown content.
 *   markdown: Raw markdown body stored in the backend.
 *
 * Returns:
 *   JSX.Element: Panel wrapper around rendered markdown.
 *
 * Raises:
 *   This component does not raise errors directly.
 */
function ProfileDocumentSection({
  title,
  markdown,
}: {
  title: string;
  markdown: string;
}) {
  return (
    <article className="profile-document-section">
      <h3>{title}</h3>
      <MarkdownContent markdown={markdown} />
    </article>
  );
}

/**
 * Render one profile summary stat.
 *
 * Parameters:
 *   label: Visible summary label.
 *   value: Visible summary value.
 *
 * Returns:
 *   JSX.Element: Compact profile stat tile.
 *
 * Raises:
 *   This component does not raise errors directly.
 */
function ProfileStat({ label, value }: { label: string; value: string }) {
  return (
    <article className="profile-stat">
      <span>{label}</span>
      <strong>{value}</strong>
    </article>
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
 * Render a table heading with a styled optional unit line.
 *
 * Parameters:
 *   label: Main label shown in the table header.
 *   unit: Optional supporting unit copy.
 *
 * Returns:
 *   JSX.Element: Structured table heading label.
 *
 * Raises:
 *   This component does not raise errors directly.
 */
function ProductsTableHeading({
  label,
  unit,
}: {
  label: string;
  unit?: string;
}) {
  return (
    <span
      className="products-table-heading"
      aria-label={unit ? `${label} ${unit}` : label}
    >
      <span className="products-table-heading-label">{label}</span>
      {unit ? (
        <span className="products-table-heading-unit">{unit}</span>
      ) : null}
    </span>
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
  tone,
  current,
  target,
  remainder,
  unit,
}: {
  title: string;
  tone: ProgressTone;
  current: number;
  target: number | null;
  remainder: number | null;
  unit: "kcal" | "g";
}) {
  const progress = target ? Math.min((current / target) * 100, 100) : 0;
  const overflow = target && current > target ? Math.min(((current - target) / target) * 100, 100) : 0;

  return (
    <article className={`progress-panel tone-${tone}${overflow > 0 ? " over-target" : ""}`}>
      <div className="panel-header">
        <h3>{title}</h3>
        <span className={`progress-target tone-${tone}`}>
          {target ? `Target ${Math.round(target)} ${unit}` : "No target"}
        </span>
      </div>
      <strong>
        {Math.round(current)} {unit}
      </strong>
      <div className="progress-track" aria-hidden="true">
        <div className={`progress-fill tone-${tone}`} style={{ width: `${progress}%` }} />
        {overflow > 0 ? (
          <div className="progress-overflow" style={{ width: `${overflow}%` }} />
        ) : null}
      </div>
      <p>{formatProgressRemainder(remainder, unit)}</p>
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
 * Toggle one meal identifier inside the open accordion state.
 *
 * Parameters:
 *   current: Currently open meal identifiers.
 *   mealId: Meal identifier to toggle.
 *
 * Returns:
 *   string[]: Updated open meal identifiers.
 *
 * Raises:
 *   This helper does not raise errors directly.
 */
function toggleMeal(current: string[], mealId: string): string[] {
  if (current.includes(mealId)) {
    return current.filter((currentId) => currentId !== mealId);
  }

  return [...current, mealId];
}

/**
 * Format a compact nutrient amount for meal summaries and ingredient rows.
 *
 * Parameters:
 *   value: Numeric value to format.
 *   unit: Unit suffix to append.
 *
 * Returns:
 *   string: Rounded compact amount string.
 *
 * Raises:
 *   This helper does not raise errors directly.
 */
function formatCompactAmount(value: number, unit: "g" | "kcal"): string {
  const roundedValue =
    unit === "kcal" ? Math.round(value) : Number(value.toFixed(value < 10 ? 1 : 0));
  return `${roundedValue} ${unit}`;
}

/**
 * Format a current-versus-target label for compact summary chips.
 *
 * Parameters:
 *   current: Logged value for the day.
 *   target: Optional planned target for the day.
 *   unit: Unit suffix shared by the value and target.
 *
 * Returns:
 *   string: Readable current/target label.
 *
 * Raises:
 *   This helper does not raise errors directly.
 */
function formatCurrentTargetValue(
  current: number,
  target: number | null,
  unit: "g" | "kcal",
): string {
  const currentValue =
    unit === "kcal"
      ? Math.round(current).toLocaleString()
      : Math.round(current).toLocaleString();

  if (target === null) {
    return `${currentValue} ${unit}`;
  }

  return `${currentValue} / ${Math.round(target).toLocaleString()} ${unit}`;
}

/**
 * Format the supporting copy shown under a progress panel.
 *
 * Parameters:
 *   remainder: Remaining target value, or `null` when no target exists.
 *   unit: Unit suffix to append.
 *
 * Returns:
 *   string: Progress support label for remaining or exceeded values.
 *
 * Raises:
 *   This helper does not raise errors directly.
 */
function formatProgressRemainder(
  remainder: number | null,
  unit: "g" | "kcal",
): string {
  if (remainder === null) {
    return "Target not set yet.";
  }

  if (remainder < 0) {
    return `Exceeded by ${Math.round(Math.abs(remainder))} ${unit}`;
  }

  return `${Math.round(remainder)} ${unit} remaining`;
}

/**
 * Format a numeric table value while preserving empty states.
 *
 * Parameters:
 *   value: Numeric value to format, or `null` when missing.
 *   suffix: Unit suffix to append.
 *
 * Returns:
 *   string: Table-safe formatted value.
 *
 * Raises:
 *   This helper does not raise errors directly.
 */
function formatTableValue(value: number | null, suffix: string): string {
  if (value === null) {
    return "Not set";
  }

  const roundedValue =
    Number.isInteger(value) || Math.abs(value) >= 10
      ? value.toFixed(0)
      : value.toFixed(1);
  return `${roundedValue} ${suffix}`;
}

/**
 * Format the reuse count for one food product.
 *
 * Parameters:
 *   usageCount: Number of meal-item logs that reused the product.
 *
 * Returns:
 *   string: Table-safe formatted usage count.
 *
 * Raises:
 *   This helper does not raise errors directly.
 */
function formatUsageCount(usageCount: number): string {
  return Math.max(0, Math.round(usageCount)).toLocaleString();
}

/**
 * Format the meals and activities count summary for one history day.
 *
 * Parameters:
 *   mealsCount: Number of meals logged.
 *   activitiesCount: Number of activities logged.
 *
 * Returns:
 *   string: Short readable count summary.
 *
 * Raises:
 *   This helper does not raise errors directly.
 */
function formatTrackedCounts(
  mealsCount: number,
  activitiesCount: number,
): string {
  const mealLabel = mealsCount === 1 ? "meal" : "meals";
  const activityLabel = activitiesCount === 1 ? "activity" : "activities";
  return `${mealsCount} ${mealLabel} • ${activitiesCount} ${activityLabel}`;
}

/**
 * Format the inclusive date range for a stored plan.
 *
 * Parameters:
 *   startDate: First ISO date in the plan.
 *   endDate: Last ISO date in the plan.
 *
 * Returns:
 *   string: Readable date range label.
 *
 * Raises:
 *   This helper does not raise errors directly.
 */
function formatPlanDateRange(startDate: string, endDate: string): string {
  if (startDate === endDate) {
    return formatLongDate(startDate);
  }

  return `${formatShortDate(startDate)} - ${formatShortDate(endDate)}`;
}

/**
 * Build Monday-first calendar cells for one plan date range.
 *
 * Parameters:
 *   startDate: First ISO date in the plan.
 *   endDate: Last ISO date in the plan.
 *
 * Returns:
 *   Array<string | null>: ISO dates plus leading blank cells.
 *
 * Raises:
 *   This helper does not raise errors directly.
 */
function getPlanCalendarCells(startDate: string, endDate: string): Array<string | null> {
  const cells: Array<string | null> = [];
  const start = new Date(`${startDate}T00:00:00`);
  const end = new Date(`${endDate}T00:00:00`);
  const mondayFirstIndex = (start.getDay() + 6) % 7;

  for (let index = 0; index < mondayFirstIndex; index += 1) {
    cells.push(null);
  }

  const cursor = new Date(start);
  while (cursor <= end) {
    const year = cursor.getFullYear();
    const month = String(cursor.getMonth() + 1).padStart(2, "0");
    const day = String(cursor.getDate()).padStart(2, "0");
    cells.push(`${year}-${month}-${day}`);
    cursor.setDate(cursor.getDate() + 1);
  }

  return cells;
}

/**
 * Return whether a JSON value has useful display content.
 *
 * Parameters:
 *   value: Unknown JSON value from the plan payload.
 *
 * Returns:
 *   boolean: `true` when the value should be rendered.
 *
 * Raises:
 *   This helper does not raise errors directly.
 */
function hasDisplayValue(value: unknown): boolean {
  if (value === null || value === undefined) {
    return false;
  }

  if (typeof value === "string") {
    return value.trim().length > 0;
  }

  if (Array.isArray(value)) {
    return value.length > 0;
  }

  if (typeof value === "object") {
    return Object.keys(value).length > 0;
  }

  return true;
}

/**
 * Format a JSON object into compact human-readable text.
 *
 * Parameters:
 *   value: Object-shaped JSON value.
 *
 * Returns:
 *   string: Comma-separated key/value summary.
 *
 * Raises:
 *   This helper does not raise errors directly.
 */
function formatJsonObject(value: Record<string, unknown>): string {
  return Object.entries(value)
    .filter(([, entryValue]) => hasDisplayValue(entryValue))
    .map(([key, entryValue]) => `${formatMetricTypeLabel(key)}: ${formatJsonValue(entryValue)}`)
    .join(", ");
}

/**
 * Format one JSON value for a structured plan section.
 *
 * Parameters:
 *   value: Unknown JSON value from a plan field.
 *
 * Returns:
 *   string: Human-readable representation.
 *
 * Raises:
 *   This helper does not raise errors directly.
 */
function formatJsonValue(value: unknown): string {
  if (typeof value === "string") {
    return value;
  }

  if (typeof value === "number" || typeof value === "boolean") {
    return String(value);
  }

  if (Array.isArray(value)) {
    return value.map((item) => formatJsonValue(item)).join(", ");
  }

  if (value && typeof value === "object") {
    return formatJsonObject(value as Record<string, unknown>);
  }

  return "n/a";
}

/**
 * Return whether one product matches the current search term.
 *
 * Parameters:
 *   product: Food product being considered.
 *   searchTerm: Lowercased search term entered by the user.
 *
 * Returns:
 *   boolean: `true` when the product name contains the search term.
 *
 * Raises:
 *   This helper does not raise errors directly.
 */
function matchesProductSearch(
  product: FoodProduct,
  searchTerm: string,
): boolean {
  if (!searchTerm) {
    return true;
  }

  return product.name.toLowerCase().includes(searchTerm);
}

/**
 * Return a sorted copy of the product catalog.
 *
 * Parameters:
 *   products: Product rows to sort.
 *   sortKey: Product field used for sorting.
 *   sortDirection: Whether the sort should be ascending or descending.
 *
 * Returns:
 *   FoodProduct[]: Sorted product rows.
 *
 * Raises:
 *   This helper does not raise errors directly.
 */
function sortProducts(
  products: FoodProduct[],
  sortKey: ProductsSortKey,
  sortDirection: SortDirection,
): FoodProduct[] {
  return [...products].sort((leftProduct, rightProduct) => {
    if (sortKey === "name") {
      const comparison = leftProduct.name.localeCompare(rightProduct.name);
      return sortDirection === "asc" ? comparison : comparison * -1;
    }

    const leftValue = getProductSortValue(leftProduct, sortKey);
    const rightValue = getProductSortValue(rightProduct, sortKey);

    if (leftValue === null && rightValue === null) {
      return 0;
    }

    if (leftValue === null) {
      return 1;
    }

    if (rightValue === null) {
      return -1;
    }

    return sortDirection === "asc"
      ? leftValue - rightValue
      : rightValue - leftValue;
  });
}

/**
 * Read the numeric sort value for one product field.
 *
 * Parameters:
 *   product: Product row being sorted.
 *   sortKey: Numeric field requested by the products table.
 *
 * Returns:
 *   number | null: Numeric sort value, or `null` when not set.
 *
 * Raises:
 *   This helper does not raise errors directly.
 */
function getProductSortValue(
  product: FoodProduct,
  sortKey: Exclude<ProductsSortKey, "name">,
): number | null {
  return product[sortKey];
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
function getTrendMetricMeta(metric: BuiltInTrendMetric) {
  if (metric === "exercise") {
    return {
      label: "Exercise calories",
      subtitle: "Daily logged exercise burn",
      color: "#60A5FA",
      targetColor: "#CBD5E1",
      valueLabel: "Achieved",
      targetLabel: null,
      pickValue: (day: HistoryDay) => day.actual_exercise_calories,
      pickTarget: () => null,
      formatValue: (value: number) => formatCalories(value),
    };
  }

  if (metric === "protein") {
    return {
      label: "Protein intake",
      subtitle: "Daily protein intake against the stored target",
      color: "#2563EB",
      targetColor: "#CBD5E1",
      valueLabel: "Achieved",
      targetLabel: "Target",
      pickValue: (day: HistoryDay) => day.actual_protein_g,
      pickTarget: (day: HistoryDay) => day.target_protein_g,
      formatValue: (value: number) => `${Math.round(value)} g`,
    };
  }

  if (metric === "carbs") {
    return {
      label: "Carbs intake",
      subtitle: "Daily carbohydrate intake against the stored target",
      color: "#D97706",
      targetColor: "#CBD5E1",
      valueLabel: "Achieved",
      targetLabel: "Target",
      pickValue: (day: HistoryDay) => day.actual_carbs_g,
      pickTarget: (day: HistoryDay) => day.target_carbs_g,
      formatValue: (value: number) => `${Math.round(value)} g`,
    };
  }

  if (metric === "fat") {
    return {
      label: "Fat intake",
      subtitle: "Daily fat intake against the stored target",
      color: "#EF4444",
      targetColor: "#CBD5E1",
      valueLabel: "Achieved",
      targetLabel: "Target",
      pickValue: (day: HistoryDay) => day.actual_fat_g,
      pickTarget: (day: HistoryDay) => day.target_fat_g,
      formatValue: (value: number) => `${Math.round(value)} g`,
    };
  }

  if (metric === "load") {
    return {
      label: "Training load",
      subtitle: "Daily suffer score from logged activities",
      color: "#FB7185",
      targetColor: "#CBD5E1",
      valueLabel: "Achieved",
      targetLabel: null,
      pickValue: (day: HistoryDay) => day.total_suffer_score,
      pickTarget: () => null,
      formatValue: (value: number) => Math.round(value).toLocaleString(),
    };
  }

  return {
    label: "Food calories",
    subtitle: "Daily food intake against the stored target",
    color: "#2DD4BF",
    targetColor: "#CBD5E1",
    valueLabel: "Achieved",
    targetLabel: "Target",
    pickValue: (day: HistoryDay) => day.actual_food_calories,
    pickTarget: (day: HistoryDay) => day.target_food_calories,
    formatValue: (value: number) => formatCalories(value),
  };
}

/**
 * Return the selected dynamic daily metric series when it is available.
 *
 * Parameters:
 *   trendMetric: Currently selected trend metric key.
 *   dailyMetrics: Dynamic daily metric series from the backend.
 *
 * Returns:
 *   DailyMetricSeries | null: Matching dynamic series, or `null`.
 *
 * Raises:
 *   This helper does not raise errors directly.
 */
function getSelectedDailyMetric(
  trendMetric: TrendMetric,
  dailyMetrics: DailyMetricSeries[],
): DailyMetricSeries | null {
  if (!isDailyTrendMetric(trendMetric)) {
    return null;
  }

  const metricType = trendMetric.replace("daily_metric:", "");
  return (
    dailyMetrics.find((dailyMetric) => dailyMetric.metric_type === metricType) ??
    null
  );
}

/**
 * Return whether a trend metric key represents a dynamic daily metric.
 *
 * Parameters:
 *   trendMetric: Trend metric key selected in the toolbar.
 *
 * Returns:
 *   boolean: `true` when the metric key points at `daily_metrics`.
 *
 * Raises:
 *   This helper does not raise errors directly.
 */
function isDailyTrendMetric(
  trendMetric: TrendMetric,
): trendMetric is DailyTrendMetric {
  return trendMetric.startsWith("daily_metric:");
}

/**
 * Build the stable toolbar key for one dynamic daily metric type.
 *
 * Parameters:
 *   metricType: Raw metric type from Supabase.
 *
 * Returns:
 *   DailyTrendMetric: UI key used by the Trends toolbar.
 *
 * Raises:
 *   This helper does not raise errors directly.
 */
function getDailyMetricKey(metricType: string): DailyTrendMetric {
  return `daily_metric:${metricType}` as DailyTrendMetric;
}

/**
 * Return the display configuration for one dynamic daily metric.
 *
 * Parameters:
 *   metricType: Raw metric type from Supabase.
 *   metricIndex: Position of the metric series in the backend response.
 *
 * Returns:
 *   Object with label, subtitle, color, and value formatting helpers.
 *
 * Raises:
 *   This helper does not raise errors directly.
 */
function getDailyMetricMeta(metricType: string, metricIndex: number) {
  const label = formatMetricTypeLabel(metricType);
  const color =
    DAILY_METRIC_COLORS[
      Math.max(0, metricIndex) % DAILY_METRIC_COLORS.length
    ];

  return {
    label,
    subtitle: `Daily ${label.toLowerCase()} from Supabase metrics`,
    color,
    targetColor: "#CBD5E1",
    valueLabel: "Value",
    targetLabel: null,
    pickValue: () => 0,
    pickTarget: () => null,
    formatValue: (value: number) => formatDailyMetricValue(metricType, value),
  };
}

/**
 * Convert a raw metric type into a readable label.
 *
 * Parameters:
 *   metricType: Raw metric type from Supabase, usually snake_case.
 *
 * Returns:
 *   string: Human-readable metric label.
 *
 * Raises:
 *   This helper does not raise errors directly.
 */
function formatMetricTypeLabel(metricType: string): string {
  const words = metricType
    .replace(/[_-]+/g, " ")
    .trim()
    .split(/\s+/)
    .filter(Boolean);

  if (words.length === 0) {
    return "Daily metric";
  }

  return words
    .map((word, index) =>
      index === 0
        ? word.charAt(0).toUpperCase() + word.slice(1).toLowerCase()
        : word.toLowerCase(),
    )
    .join(" ");
}

/**
 * Format a dynamic daily metric value with a best-effort unit.
 *
 * Parameters:
 *   metricType: Raw metric type from Supabase.
 *   value: Numeric metric value for one date.
 *
 * Returns:
 *   string: Compact value display for the trend tooltip.
 *
 * Raises:
 *   This helper does not raise errors directly.
 */
function formatDailyMetricValue(metricType: string, value: number): string {
  const formattedValue =
    Number.isInteger(value) || Math.abs(value) >= 10
      ? value.toFixed(0)
      : value.toFixed(1);
  const normalizedType = metricType.toLowerCase();

  if (normalizedType.includes("hour")) {
    return `${formattedValue} h`;
  }

  if (normalizedType.includes("calorie") || normalizedType.endsWith("kcal")) {
    return formatCalories(value);
  }

  if (normalizedType.includes("percent") || normalizedType.endsWith("_pct")) {
    return `${formattedValue}%`;
  }

  return formattedValue;
}
