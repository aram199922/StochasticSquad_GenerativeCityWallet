import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  BadgePercent,
  Bike,
  Building2,
  CheckCircle2,
  Clock,
  Coffee,
  LandPlot,
  Loader2,
  MapPin,
  PartyPopper,
  QrCode,
  Sparkles,
  Store,
  Ticket,
  Train,
  Umbrella,
  WalletCards,
  X,
} from "lucide-react";
import { Link } from "react-router-dom";
import type { CSSProperties } from "react";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

type DynamicOffer = {
  headline: string;
  description: string;
  discount_value: string;
  tone: string;
  offer_token: string;
  ui_styling: {
    primary_color: string;
    background_gradient: string;
    icon_name: string;
  };
};

type ApiResponse = {
  scenario_id: string;
  timestamp: string;
  time_period: string;
  offer_token: string;
  offer_details: {
    headline: string;
    description: string;
    discount_value: string;
    tone: string;
  };
  ui_styling: {
    primary_color: string;
    background_gradient: string;
    icon_name: string;
  };
  context_snapshot?: {
    weather: { condition: string; temperature: number; is_raining: boolean };
    active_events: string[];
    featured_merchant: {
      name: string;
      category: string;
      address: string;
      max_discount_percent: number;
    };
  };
};

// ---------------------------------------------------------------------------
// Icon registry
// ---------------------------------------------------------------------------

const iconRegistry = {
  ticket: Ticket,
  train: Train,
  coffee: Coffee,
  bike: Bike,
  landmark: LandPlot,
  city: Building2,
  wallet: WalletCards,
  percent: BadgePercent,
  "umbrella-cozy": Umbrella,
  "confetti-star": PartyPopper,
  "hot-drink": Coffee,
  "city-spark": Sparkles,
} as const;

type IconName = keyof typeof iconRegistry;

// ---------------------------------------------------------------------------
// Static fallback offer
// ---------------------------------------------------------------------------

const FALLBACK_OFFER: DynamicOffer = {
  headline: "Museum Mile Evening Pass",
  description:
    "Unlock late entry, metro transfer credit, and a neighborhood café reward for tonight's cultural route.",
  discount_value: "32%",
  tone: "premium",
  offer_token: "",
  ui_styling: {
    primary_color: "hsl(176 62% 52%)",
    background_gradient:
      "linear-gradient(145deg, hsl(224 34% 7%) 0%, hsl(221 47% 16%) 48%, hsl(176 54% 28%) 100%)",
    icon_name: "landmark",
  },
};

const OFFER_DURATION_SECONDS = 15 * 60; // 15-minute offer window

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function mapApiResponse(data: ApiResponse): DynamicOffer {
  return {
    headline: data.offer_details.headline,
    description: data.offer_details.description,
    discount_value: data.offer_details.discount_value,
    tone: data.offer_details.tone,
    offer_token: data.offer_token ?? "",
    ui_styling: {
      primary_color: data.ui_styling.primary_color,
      background_gradient: data.ui_styling.background_gradient,
      icon_name: data.ui_styling.icon_name,
    },
  };
}

function formatTime(seconds: number): string {
  const m = Math.floor(seconds / 60)
    .toString()
    .padStart(2, "0");
  const s = (seconds % 60).toString().padStart(2, "0");
  return `${m}:${s}`;
}

// ---------------------------------------------------------------------------
// DynamicOfferWidget
// ---------------------------------------------------------------------------

type OfferState = "live" | "claimed" | "dismissed" | "expired";

function DynamicOfferWidget({
  offer,
  isLoading,
  timeLeft,
  offerState,
  onClaim,
  onDismiss,
}: {
  offer: DynamicOffer;
  isLoading: boolean;
  timeLeft: number;
  offerState: OfferState;
  onClaim: () => void;
  onDismiss: () => void;
}) {
  const OfferIcon =
    iconRegistry[offer.ui_styling.icon_name as IconName] ?? Sparkles;

  const offerStyle = useMemo(
    () =>
      ({
        "--offer-primary": offer.ui_styling.primary_color,
        "--offer-gradient": offer.ui_styling.background_gradient,
      }) as CSSProperties,
    [offer.ui_styling.background_gradient, offer.ui_styling.primary_color],
  );

  const accentStyle: CSSProperties = {
    backgroundColor: offer.ui_styling.primary_color,
    boxShadow: `0 8px 24px -4px ${offer.ui_styling.primary_color}55`,
  };

  const iconBadgeStyle: CSSProperties = {
    boxShadow: `0 0 0 1px ${offer.ui_styling.primary_color}44`,
  };

  // Urgency colour for the timer
  const timerUrgent = timeLeft <= 120 && offerState === "live";

  if (offerState === "dismissed") {
    return (
      <section
        aria-label="Offer dismissed"
        className="relative flex min-h-[400px] flex-col items-center justify-center gap-4 overflow-hidden rounded-[2rem] border border-wallet-line bg-card p-10 text-muted-foreground"
      >
        <X className="h-10 w-10 opacity-30" />
        <p className="text-lg font-semibold">Offer dismissed</p>
        <p className="text-sm">A new offer will appear next time you open City-Wallet.</p>
      </section>
    );
  }

  if (offerState === "expired") {
    return (
      <section
        aria-label="Offer expired"
        className="relative flex min-h-[400px] flex-col items-center justify-center gap-4 overflow-hidden rounded-[2rem] border border-wallet-line bg-card p-10 text-muted-foreground"
      >
        <Clock className="h-10 w-10 opacity-30" />
        <p className="text-lg font-semibold">Offer expired</p>
        <p className="text-sm">This offer was only valid for 15 minutes. Refresh for a new one.</p>
      </section>
    );
  }

  return (
    <section
      aria-label="Dynamic offer widget"
      style={offerStyle}
      className="relative overflow-hidden rounded-[2rem] bg-[image:var(--offer-gradient)] p-5 text-primary-foreground wallet-shadow transition-transform duration-500 hover:-translate-y-1 sm:p-7"
    >
      <div className="absolute inset-0 opacity-60 [background:radial-gradient(circle_at_20%_15%,var(--offer-primary),transparent_28%),radial-gradient(circle_at_88%_18%,hsl(var(--accent)/0.35),transparent_24%)]" />
      <div className="absolute -right-24 top-16 h-64 w-64 rounded-full border border-primary-foreground/15" />
      <div className="absolute inset-x-6 top-0 h-px overflow-hidden bg-primary-foreground/20">
        <span className="block h-full w-1/2 animate-shimmer bg-primary-foreground/60" />
      </div>

      <div className="relative z-10 flex min-h-[520px] flex-col justify-between gap-8 sm:min-h-[560px]">
        {/* ── Header row ── */}
        <div className="flex items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <div
              style={iconBadgeStyle}
              className="grid h-12 w-12 place-items-center rounded-2xl bg-primary-foreground/12 backdrop-blur"
            >
              {isLoading ? (
                <Loader2 className="h-6 w-6 animate-spin" aria-hidden="true" />
              ) : (
                <OfferIcon className="h-6 w-6" aria-hidden="true" />
              )}
            </div>
            <div>
              <p className="text-sm font-semibold uppercase tracking-[0.18em] text-primary-foreground/68">
                City-Wallet
              </p>
              <p className="text-sm text-primary-foreground/72">
                {isLoading ? "Generating offer…" : `Live offer · ${offer.tone}`}
              </p>
            </div>
          </div>

          {/* Dismiss button */}
          {!isLoading && offerState === "live" && (
            <button
              type="button"
              onClick={onDismiss}
              aria-label="Dismiss offer"
              className="grid h-9 w-9 place-items-center rounded-full bg-primary-foreground/12 text-primary-foreground/60 backdrop-blur transition-all hover:bg-primary-foreground/24 hover:text-primary-foreground"
            >
              <X className="h-4 w-4" />
            </button>
          )}

          {offerState === "live" && !isLoading && (
            <WalletCards
              className="h-7 w-7 text-primary-foreground/75"
              aria-hidden="true"
            />
          )}
        </div>

        {/* ── Offer copy ── */}
        <div className="space-y-5">
          <div className="inline-flex items-center gap-2 rounded-full bg-primary-foreground/12 px-3 py-1.5 text-sm font-semibold text-primary-foreground ring-1 ring-primary-foreground/16 backdrop-blur">
            <Sparkles className="h-4 w-4" aria-hidden="true" />
            Generative route reward
          </div>
          <div className="max-w-xl space-y-4">
            <h1 className="font-display text-4xl font-black leading-[0.98] tracking-normal text-primary-foreground sm:text-6xl">
              {offer.headline}
            </h1>
            <p className="text-base leading-7 text-primary-foreground/76 sm:text-lg">
              {offer.description}
            </p>
          </div>
        </div>

        {/* ── CTA row ── */}
        <div className="grid gap-4 lg:grid-cols-[1fr_220px] lg:items-end">
          <div className="rounded-[1.5rem] bg-primary-foreground/10 p-4 ring-1 ring-primary-foreground/16 backdrop-blur-xl">
            <div className="flex items-end justify-between gap-4">
              <div>
                <p className="text-sm text-primary-foreground/68">Instant value</p>
                <p className="text-6xl font-black leading-none text-primary-foreground sm:text-7xl">
                  {offer.discount_value}
                </p>
              </div>

              {/* Expiry timer */}
              <div
                className={`flex flex-col items-end gap-1 ${timerUrgent ? "text-red-300" : "text-primary-foreground/60"}`}
              >
                <Clock className="h-4 w-4" />
                <span className="text-sm font-bold tabular-nums">
                  {offerState === "live" ? formatTime(timeLeft) : "—"}
                </span>
                <span className="text-[10px] uppercase tracking-wide opacity-70">
                  expires
                </span>
              </div>
            </div>

            {offerState === "live" && (
              <button
                type="button"
                onClick={onClaim}
                disabled={isLoading}
                style={accentStyle}
                className="mt-4 group inline-flex w-full min-h-12 items-center justify-center gap-2 whitespace-nowrap rounded-full px-5 py-3 text-sm font-extrabold text-white transition-all duration-300 hover:scale-[1.03] hover:brightness-110 active:scale-[0.98] disabled:opacity-50 disabled:cursor-not-allowed"
              >
                <QrCode
                  className="h-4 w-4 transition-transform duration-300 group-hover:rotate-12"
                  aria-hidden="true"
                />
                Claim Offer
              </button>
            )}

            {offerState === "claimed" && (
              <div className="mt-4 flex items-center gap-2 rounded-full bg-green-500/20 px-4 py-3 text-sm font-bold text-green-300 ring-1 ring-green-500/30">
                <CheckCircle2 className="h-4 w-4" />
                Offer claimed — show QR at checkout
              </div>
            )}
          </div>

          {/* QR pane */}
          {offerState === "claimed" ? (
            <div className="animate-qr-rise rounded-[1.5rem] bg-primary-foreground p-4 text-wallet-ink shadow-2xl shadow-wallet-ink/30">
              <div className="grid aspect-square place-items-center rounded-2xl bg-[linear-gradient(135deg,hsl(var(--muted)),hsl(var(--card)))] p-3">
                <div className="grid h-full w-full grid-cols-5 grid-rows-5 gap-1">
                  {Array.from({ length: 25 }).map((_, index) => (
                    <span
                      key={index}
                      className={`rounded-[0.28rem] ${
                        [0, 1, 3, 5, 6, 7, 10, 12, 14, 17, 18, 19, 21, 23, 24].includes(index)
                          ? "bg-wallet-ink"
                          : "bg-transparent"
                      }`}
                    />
                  ))}
                </div>
              </div>
              <p className="mt-3 text-center text-xs font-bold uppercase tracking-[0.18em] text-muted-foreground">
                Scan to redeem
              </p>
            </div>
          ) : (
            <div className="hidden rounded-[1.5rem] border border-primary-foreground/14 bg-primary-foreground/8 p-4 text-primary-foreground/68 backdrop-blur lg:block">
              <QrCode className="mb-8 h-8 w-8" aria-hidden="true" />
              <p className="text-sm leading-6">QR code appears here after claim.</p>
            </div>
          )}
        </div>
      </div>
    </section>
  );
}

// ---------------------------------------------------------------------------
// Context snapshot sidebar card
// ---------------------------------------------------------------------------

function ContextSnapshotCard({
  snapshot,
  scenarioId,
  timePeriod,
}: {
  snapshot: ApiResponse["context_snapshot"];
  scenarioId: string | null;
  timePeriod: string | null;
}) {
  if (!snapshot) return null;

  const scenarioLabels: Record<string, string> = {
    SHELTER_SEEKER: "Shelter Seeker",
    FESTIVAL_VIBE: "Festival Vibe",
    COZY_WEATHER: "Cozy Weather",
    NORMAL_CITY_FLOW: "Normal City Flow",
  };

  return (
    <div className="glass-panel soft-shadow rounded-[2rem] border border-wallet-line p-5 space-y-4">
      <div className="flex items-center justify-between">
        <p className="text-sm font-bold uppercase tracking-[0.16em] text-muted-foreground">
          Live context
        </p>
        {scenarioId && (
          <span className="rounded-full bg-secondary/20 px-2.5 py-1 text-xs font-bold text-secondary">
            {scenarioLabels[scenarioId] ?? scenarioId}
          </span>
        )}
      </div>

      {/* Weather row */}
      <div className="flex items-center gap-3 rounded-2xl border border-wallet-line bg-card/70 p-3">
        <div className="grid h-9 w-9 place-items-center rounded-xl bg-muted text-foreground">
          <Umbrella className="h-4 w-4" />
        </div>
        <div>
          <p className="text-xs text-muted-foreground capitalize">
            {snapshot.weather.condition} · {timePeriod}
          </p>
          <p className="font-bold text-foreground">
            {snapshot.weather.temperature}°C
            {snapshot.weather.is_raining && " · Raining"}
          </p>
        </div>
      </div>

      {/* Featured merchant */}
      {snapshot.featured_merchant?.name && (
        <div className="flex items-center gap-3 rounded-2xl border border-wallet-line bg-card/70 p-3">
          <div className="grid h-9 w-9 place-items-center rounded-xl bg-muted text-foreground">
            <Store className="h-4 w-4" />
          </div>
          <div className="min-w-0">
            <p className="text-xs text-muted-foreground">Featured merchant</p>
            <p className="truncate font-bold text-foreground">
              {snapshot.featured_merchant.name}
            </p>
            <p className="truncate text-xs text-muted-foreground">
              {snapshot.featured_merchant.address}
            </p>
          </div>
        </div>
      )}

      {/* Events */}
      {snapshot.active_events.length > 0 && (
        <div className="rounded-2xl border border-wallet-line bg-card/70 p-3">
          <p className="mb-2 text-xs font-semibold text-muted-foreground uppercase tracking-wide">
            Active events
          </p>
          <ul className="space-y-1">
            {snapshot.active_events.slice(0, 3).map((ev) => (
              <li key={ev} className="text-sm text-foreground truncate">
                · {ev}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------

const companionOffers = [
  { label: "Transit", value: "$8 credit", icon: Train },
  { label: "Coffee", value: "2-for-1", icon: Coffee },
  { label: "Bike dock", value: "45 min", icon: Bike },
];

const Index = () => {
  const [offerData, setOfferData] = useState<DynamicOffer>(FALLBACK_OFFER);
  const [scenarioId, setScenarioId] = useState<string | null>(null);
  const [timePeriod, setTimePeriod] = useState<string | null>(null);
  const [contextSnapshot, setContextSnapshot] =
    useState<ApiResponse["context_snapshot"]>(undefined);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [offerState, setOfferState] = useState<OfferState>("live");
  const [timeLeft, setTimeLeft] = useState(OFFER_DURATION_SECONDS);

  const offerTokenRef = useRef<string>("");
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // Countdown timer — starts once an offer is loaded
  useEffect(() => {
    if (isLoading || offerState !== "live") return;

    timerRef.current = setInterval(() => {
      setTimeLeft((prev) => {
        if (prev <= 1) {
          clearInterval(timerRef.current!);
          setOfferState("expired");
          // Fire-and-forget dismiss so stats stay accurate
          if (offerTokenRef.current) {
            fetch(`${import.meta.env.VITE_API_URL}/dismiss`, {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({ token: offerTokenRef.current }),
            }).catch(() => {});
          }
          return 0;
        }
        return prev - 1;
      });
    }, 1000);

    return () => {
      if (timerRef.current) clearInterval(timerRef.current);
    };
  }, [isLoading, offerState]);

  // Fetch offer from backend
  useEffect(() => {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 25_000);

    const fetchOffer = async () => {
      try {
        const res = await fetch(
          `${import.meta.env.VITE_API_URL}/get-context`,
          { signal: controller.signal },
        );

        if (!res.ok) {
          throw new Error(`Server responded with status ${res.status}`);
        }

        const data: ApiResponse = await res.json();
        setOfferData(mapApiResponse(data));
        setScenarioId(data.scenario_id);
        setTimePeriod(data.time_period ?? null);
        setContextSnapshot(data.context_snapshot);
        offerTokenRef.current = data.offer_token ?? "";
        setTimeLeft(OFFER_DURATION_SECONDS);
        setOfferState("live");
        setError(null);
      } catch (err) {
        if (err instanceof Error && err.name === "AbortError") return;
        console.error("Failed to fetch offer:", err);
        setError(
          "Could not reach the City-Wallet server. Showing a sample offer.",
        );
      } finally {
        setIsLoading(false);
      }
    };

    fetchOffer();
    return () => {
      clearTimeout(timeoutId);
      controller.abort();
    };
  }, []);

  const handleClaim = useCallback(async () => {
    setOfferState("claimed");
    if (timerRef.current) clearInterval(timerRef.current);

    if (offerTokenRef.current) {
      try {
        await fetch(`${import.meta.env.VITE_API_URL}/redeem`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ token: offerTokenRef.current }),
        });
      } catch {
        // Non-fatal — QR is already shown to the user
      }
    }
  }, []);

  const handleDismiss = useCallback(async () => {
    setOfferState("dismissed");
    if (timerRef.current) clearInterval(timerRef.current);

    if (offerTokenRef.current) {
      try {
        await fetch(`${import.meta.env.VITE_API_URL}/dismiss`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ token: offerTokenRef.current }),
        });
      } catch {
        // Non-fatal
      }
    }
  }, []);

  return (
    <main className="min-h-screen px-4 py-5 sm:px-6 lg:px-10">
      {/* Top nav */}
      <div className="mx-auto mb-6 flex max-w-7xl items-center justify-between">
        <div className="flex items-center gap-2">
          <WalletCards className="h-5 w-5 text-secondary" />
          <span className="font-bold text-foreground">City-Wallet</span>
        </div>
        <Link
          to="/merchant"
          className="flex items-center gap-1.5 rounded-full border border-wallet-line bg-card/70 px-3 py-1.5 text-xs font-semibold text-muted-foreground backdrop-blur transition-colors hover:text-foreground"
        >
          <Store className="h-3.5 w-3.5" />
          Merchant Portal
        </Link>
      </div>

      {error && (
        <div
          role="alert"
          className="mx-auto mb-5 max-w-7xl rounded-2xl border border-destructive/30 bg-destructive/10 px-5 py-3 text-sm text-destructive"
        >
          {error}
        </div>
      )}

      <div className="mx-auto grid max-w-7xl gap-6 lg:grid-cols-[minmax(0,1fr)_380px] lg:items-start">
        <DynamicOfferWidget
          offer={offerData}
          isLoading={isLoading}
          timeLeft={timeLeft}
          offerState={offerState}
          onClaim={handleClaim}
          onDismiss={handleDismiss}
        />

        <aside className="space-y-5">
          {/* Live context snapshot — replaces static companion offers */}
          {contextSnapshot ? (
            <ContextSnapshotCard
              snapshot={contextSnapshot}
              scenarioId={scenarioId}
              timePeriod={timePeriod}
            />
          ) : (
            <div className="glass-panel soft-shadow rounded-[2rem] border border-wallet-line p-5">
              <div className="mb-5 flex items-center justify-between">
                <div>
                  <p className="text-sm font-bold uppercase tracking-[0.16em] text-muted-foreground">
                    Wallet pulse
                  </p>
                  <h2 className="mt-1 text-2xl font-black tracking-normal text-foreground">
                    Generated for your city path
                  </h2>
                </div>
                <div className="grid h-11 w-11 place-items-center rounded-2xl bg-secondary text-secondary-foreground animate-float-soft">
                  <MapPin className="h-5 w-5" aria-hidden="true" />
                </div>
              </div>
              <div className="space-y-3">
                {companionOffers.map((item) => {
                  const Icon = item.icon;
                  return (
                    <div
                      key={item.label}
                      className="flex items-center justify-between rounded-2xl border border-wallet-line bg-card/70 p-4 transition-all duration-300 hover:-translate-y-0.5 hover:bg-card"
                    >
                      <div className="flex items-center gap-3">
                        <div className="grid h-10 w-10 place-items-center rounded-xl bg-muted text-foreground">
                          <Icon className="h-5 w-5" aria-hidden="true" />
                        </div>
                        <span className="font-bold text-foreground">{item.label}</span>
                      </div>
                      <span className="text-sm font-extrabold text-secondary">
                        {item.value}
                      </span>
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          {/* Live JSON preview */}
          <div className="rounded-[2rem] border border-wallet-line bg-wallet-ink p-5 text-primary-foreground soft-shadow">
            <p className="text-sm font-semibold text-primary-foreground/62">
              {isLoading ? "Awaiting live data…" : "Live JSON payload"}
            </p>
            {scenarioId && (
              <p className="mt-1 text-xs font-bold uppercase tracking-[0.14em] text-primary-foreground/45">
                Scenario: {scenarioId}
              </p>
            )}
            <pre className="mt-3 overflow-x-auto rounded-2xl bg-primary-foreground/8 p-4 text-xs leading-6 text-primary-foreground/78">
              {isLoading
                ? "{ … }"
                : `{
  "headline": "${offerData.headline}",
  "discount_value": "${offerData.discount_value}",
  "time_period": "${timePeriod ?? "—"}",
  "offer_token": "${offerTokenRef.current ? offerTokenRef.current.slice(0, 8) + "…" : "—"}",
  "ui_styling": {
    "primary_color": "${offerData.ui_styling.primary_color}",
    "icon_name": "${offerData.ui_styling.icon_name}"
  }
}`}
            </pre>
          </div>
        </aside>
      </div>
    </main>
  );
};

export default Index;
