import { useEffect, useState } from "react";
import {
  ArrowLeft,
  BadgePercent,
  BarChart3,
  CheckCircle2,
  Clock,
  Coffee,
  Loader2,
  RefreshCw,
  Settings2,
  Store,
  TrendingUp,
  WalletCards,
  X,
  Zap,
} from "lucide-react";
import { Link } from "react-router-dom";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

type Stats = {
  total_offers: number;
  redeemed: number;
  dismissed: number;
  pending: number;
  conversion_rate: number;
  per_scenario: Record<
    string,
    { generated: number; redeemed: number; dismissed: number }
  >;
};

type Merchant = {
  id: string;
  name: string;
  category: string;
  address: string;
  current_transaction_volume: number;
  avg_hourly_transaction_volume: number;
  rules: {
    max_discount_percent: number;
    min_basket_eur: number;
    trigger_volume_threshold: number;
    offer_headline_template: string;
    emotional_framing: string;
  };
};

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const SCENARIO_LABELS: Record<string, { label: string; color: string }> = {
  SHELTER_SEEKER:   { label: "Shelter Seeker",   color: "text-orange-400"  },
  FESTIVAL_VIBE:    { label: "Festival Vibe",     color: "text-purple-400" },
  COZY_WEATHER:     { label: "Cozy Weather",      color: "text-amber-500"  },
  NORMAL_CITY_FLOW: { label: "Normal City Flow",  color: "text-sky-400"    },
};

function pct(n: number): string {
  return `${Math.round(n * 100)}%`;
}

// ---------------------------------------------------------------------------
// Stat card (simple block, no extra chrome)
// ---------------------------------------------------------------------------

function StatBlock({
  label,
  value,
  sub,
  accent,
}: {
  label: string;
  value: string | number;
  sub?: string;
  accent?: boolean;
}) {
  return (
    <div className="rounded-2xl border border-wallet-line bg-card p-4">
      <p className="text-xs font-semibold uppercase tracking-[0.14em] text-muted-foreground">
        {label}
      </p>
      <p
        className={`mt-1 text-4xl font-black leading-none ${accent ? "text-secondary" : "text-foreground"}`}
      >
        {value}
      </p>
      {sub && (
        <p className="mt-1 text-xs text-muted-foreground">{sub}</p>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Rule editor (looks editable; updates are in-memory for the demo)
// ---------------------------------------------------------------------------

function RuleEditor({ merchant }: { merchant: Merchant }) {
  const [maxDiscount, setMaxDiscount] = useState(
    merchant.rules.max_discount_percent,
  );
  const [minBasket, setMinBasket] = useState(merchant.rules.min_basket_eur);
  const [triggerVol, setTriggerVol] = useState(
    merchant.rules.trigger_volume_threshold,
  );
  const [saved, setSaved] = useState(false);

  const handleSave = () => {
    setSaved(true);
    setTimeout(() => setSaved(false), 2000);
  };

  return (
    <div className="rounded-[2rem] border border-wallet-line bg-card p-6 space-y-5">
      <div className="flex items-center gap-2">
        <Settings2 className="h-5 w-5 text-muted-foreground" />
        <h2 className="text-base font-bold text-foreground">Offer Rules</h2>
        <span className="ml-auto rounded-full bg-secondary/15 px-2.5 py-0.5 text-xs font-semibold text-secondary">
          AI reads these
        </span>
      </div>

      <p className="text-sm text-muted-foreground">
        Set the guardrails. The AI generates the creative execution within your constraints.
      </p>

      <div className="space-y-4">
        {/* Max discount */}
        <div className="space-y-1.5">
          <div className="flex items-center justify-between">
            <label className="text-sm font-semibold text-foreground">
              Max discount
            </label>
            <span className="text-sm font-bold text-secondary">{maxDiscount}%</span>
          </div>
          <input
            type="range"
            min={5}
            max={50}
            step={5}
            value={maxDiscount}
            onChange={(e) => setMaxDiscount(Number(e.target.value))}
            className="w-full accent-[hsl(var(--secondary))]"
          />
          <div className="flex justify-between text-[10px] text-muted-foreground">
            <span>5%</span><span>50%</span>
          </div>
        </div>

        {/* Min basket */}
        <div className="space-y-1.5">
          <div className="flex items-center justify-between">
            <label className="text-sm font-semibold text-foreground">
              Min basket value
            </label>
            <span className="text-sm font-bold text-secondary">€{minBasket.toFixed(2)}</span>
          </div>
          <input
            type="range"
            min={1}
            max={20}
            step={0.5}
            value={minBasket}
            onChange={(e) => setMinBasket(Number(e.target.value))}
            className="w-full accent-[hsl(var(--secondary))]"
          />
        </div>

        {/* Trigger volume threshold */}
        <div className="space-y-1.5">
          <div className="flex items-center justify-between">
            <label className="text-sm font-semibold text-foreground">
              Trigger threshold
            </label>
            <span className="text-sm font-bold text-secondary">
              {triggerVol} tx/h
            </span>
          </div>
          <input
            type="range"
            min={1}
            max={30}
            step={1}
            value={triggerVol}
            onChange={(e) => setTriggerVol(Number(e.target.value))}
            className="w-full accent-[hsl(var(--secondary))]"
          />
          <p className="text-[11px] text-muted-foreground">
            Offer fires when hourly transactions drop below this level.
          </p>
        </div>

        {/* Emotional framing badge */}
        <div className="flex items-center gap-3 rounded-xl border border-wallet-line bg-muted/40 px-4 py-3">
          <Zap className="h-4 w-4 text-accent shrink-0" />
          <div>
            <p className="text-xs font-semibold text-foreground">Emotional framing</p>
            <p className="text-xs text-muted-foreground font-mono">
              {merchant.rules.emotional_framing}
            </p>
          </div>
        </div>

        {/* Headline template */}
        <div className="rounded-xl border border-wallet-line bg-muted/40 p-3">
          <p className="text-xs font-semibold text-foreground mb-1">
            Offer headline template
          </p>
          <p className="text-sm italic text-muted-foreground">
            "{merchant.rules.offer_headline_template}"
          </p>
          <p className="mt-1.5 text-[10px] text-muted-foreground">
            The AI uses this as tone guidance, not a fixed string.
          </p>
        </div>
      </div>

      <button
        type="button"
        onClick={handleSave}
        className="flex w-full items-center justify-center gap-2 rounded-full bg-secondary py-3 text-sm font-bold text-secondary-foreground transition-all hover:brightness-110 active:scale-[0.98]"
      >
        {saved ? (
          <>
            <CheckCircle2 className="h-4 w-4" /> Saved
          </>
        ) : (
          "Save rules"
        )}
      </button>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Scenario breakdown table
// ---------------------------------------------------------------------------

function ScenarioBreakdown({ data }: { data: Stats["per_scenario"] }) {
  const entries = Object.entries(data);
  if (entries.length === 0) return null;

  return (
    <div className="rounded-[2rem] border border-wallet-line bg-card overflow-hidden">
      <div className="px-5 py-4 border-b border-wallet-line">
        <div className="flex items-center gap-2">
          <BarChart3 className="h-4 w-4 text-muted-foreground" />
          <h2 className="text-sm font-bold text-foreground">Performance by scenario</h2>
        </div>
      </div>
      <div className="divide-y divide-wallet-line">
        {entries.map(([scenario, counts]) => {
          const meta = SCENARIO_LABELS[scenario] ?? {
            label: scenario,
            color: "text-foreground",
          };
          const conv =
            counts.generated > 0
              ? Math.round((counts.redeemed / counts.generated) * 100)
              : 0;
          return (
            <div
              key={scenario}
              className="grid grid-cols-[1fr_auto_auto_auto_auto] gap-x-4 items-center px-5 py-3 text-sm"
            >
              <span className={`font-semibold ${meta.color}`}>
                {meta.label}
              </span>
              <span className="text-muted-foreground text-right">
                {counts.generated} sent
              </span>
              <span className="text-green-500 font-semibold text-right">
                {counts.redeemed} claimed
              </span>
              <span className="text-destructive text-right">
                {counts.dismissed} dismissed
              </span>
              <span className="font-bold text-foreground text-right w-12">
                {conv}%
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------

const Merchant = () => {
  const [stats, setStats] = useState<Stats | null>(null);
  const [merchants, setMerchants] = useState<Merchant[]>([]);
  const [selectedIdx, setSelectedIdx] = useState(0);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [lastUpdated, setLastUpdated] = useState<string>("");

  const loadData = async (isRefresh = false) => {
    if (isRefresh) setRefreshing(true);
    else setLoading(true);

    try {
      const [statsRes, merchantsRes] = await Promise.all([
        fetch(`${import.meta.env.VITE_API_URL}/merchant-stats`),
        fetch(`${import.meta.env.VITE_API_URL}/merchants`),
      ]);

      if (statsRes.ok) {
        const s: Stats = await statsRes.json();
        setStats(s);
      }
      if (merchantsRes.ok) {
        const m = await merchantsRes.json();
        setMerchants(m.merchants ?? []);
      }
      setLastUpdated(new Date().toLocaleTimeString());
    } catch {
      // non-fatal — show whatever we have
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  const merchant = merchants[selectedIdx];

  return (
    <main className="min-h-screen px-4 py-5 sm:px-6 lg:px-10">
      {/* Top nav */}
      <div className="mx-auto mb-8 flex max-w-7xl items-center gap-4">
        <Link
          to="/"
          className="flex items-center gap-1.5 rounded-full border border-wallet-line bg-card/70 px-3 py-1.5 text-xs font-semibold text-muted-foreground backdrop-blur transition-colors hover:text-foreground"
        >
          <ArrowLeft className="h-3.5 w-3.5" />
          User view
        </Link>
        <div className="flex items-center gap-2">
          <WalletCards className="h-5 w-5 text-secondary" />
          <span className="font-bold text-foreground">City-Wallet</span>
          <span className="text-muted-foreground">·</span>
          <span className="text-sm text-muted-foreground">Merchant Portal</span>
        </div>
        <button
          type="button"
          onClick={() => loadData(true)}
          disabled={refreshing}
          className="ml-auto flex items-center gap-1.5 rounded-full border border-wallet-line bg-card/70 px-3 py-1.5 text-xs font-semibold text-muted-foreground backdrop-blur transition-colors hover:text-foreground disabled:opacity-50"
        >
          <RefreshCw className={`h-3.5 w-3.5 ${refreshing ? "animate-spin" : ""}`} />
          {lastUpdated ? `Updated ${lastUpdated}` : "Refresh"}
        </button>
      </div>

      {loading ? (
        <div className="flex min-h-[40vh] items-center justify-center gap-3 text-muted-foreground">
          <Loader2 className="h-6 w-6 animate-spin" />
          <span>Loading merchant data…</span>
        </div>
      ) : (
        <div className="mx-auto max-w-7xl space-y-8">

          {/* ── Merchant selector ── */}
          {merchants.length > 0 && (
            <div className="flex flex-wrap gap-3">
              {merchants.map((m, i) => (
                <button
                  key={m.id}
                  type="button"
                  onClick={() => setSelectedIdx(i)}
                  className={`flex items-center gap-2 rounded-2xl border px-4 py-2.5 text-sm font-semibold transition-all ${
                    i === selectedIdx
                      ? "border-secondary bg-secondary/15 text-secondary"
                      : "border-wallet-line bg-card/70 text-muted-foreground hover:text-foreground"
                  }`}
                >
                  <Store className="h-4 w-4" />
                  {m.name}
                  <span className="rounded-full bg-muted px-2 py-0.5 text-xs font-normal">
                    {m.category}
                  </span>
                </button>
              ))}
            </div>
          )}

          {/* ── Merchant header ── */}
          {merchant && (
            <div className="flex items-start gap-4">
              <div className="grid h-14 w-14 shrink-0 place-items-center rounded-2xl bg-secondary/15 text-secondary">
                <Coffee className="h-7 w-7" />
              </div>
              <div>
                <h1 className="text-2xl font-black text-foreground">
                  {merchant.name}
                </h1>
                <p className="text-sm text-muted-foreground">{merchant.address}</p>
                <div className="mt-2 flex items-center gap-2">
                  <span className="rounded-full border border-wallet-line bg-card px-2.5 py-0.5 text-xs font-semibold text-muted-foreground">
                    {merchant.category}
                  </span>
                  <span
                    className={`rounded-full px-2.5 py-0.5 text-xs font-bold ${
                      merchant.current_transaction_volume <
                      merchant.rules.trigger_volume_threshold
                        ? "bg-orange-500/15 text-orange-400"
                        : "bg-green-500/15 text-green-400"
                    }`}
                  >
                    {merchant.current_transaction_volume <
                    merchant.rules.trigger_volume_threshold
                      ? "Quiet period — offer active"
                      : "Normal traffic"}
                  </span>
                </div>
              </div>
            </div>
          )}

          {/* ── Aggregate stats ── */}
          {stats && (
            <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
              <StatBlock
                label="Offers generated"
                value={stats.total_offers}
                sub="all time"
              />
              <StatBlock
                label="Redeemed"
                value={stats.redeemed}
                sub={`${pct(stats.redeemed / Math.max(stats.total_offers, 1))} of total`}
                accent
              />
              <StatBlock
                label="Dismissed"
                value={stats.dismissed}
                sub={`${pct(stats.dismissed / Math.max(stats.total_offers, 1))} of total`}
              />
              <StatBlock
                label="Conversion rate"
                value={pct(stats.conversion_rate)}
                sub="claimed / generated"
                accent
              />
            </div>
          )}

          {/* ── Traffic indicator ── */}
          {merchant && (
            <div className="rounded-[2rem] border border-wallet-line bg-card p-5">
              <div className="mb-4 flex items-center gap-2">
                <TrendingUp className="h-4 w-4 text-muted-foreground" />
                <h2 className="text-sm font-bold text-foreground">
                  Live transaction pulse
                </h2>
              </div>
              <div className="flex items-end gap-3">
                <div className="flex-1">
                  <div className="mb-1.5 flex justify-between text-xs text-muted-foreground">
                    <span>Current: {merchant.current_transaction_volume} tx/h</span>
                    <span>Avg: {merchant.avg_hourly_transaction_volume} tx/h</span>
                  </div>
                  <div className="h-3 w-full overflow-hidden rounded-full bg-muted">
                    <div
                      className="h-full rounded-full transition-all duration-700"
                      style={{
                        width: `${Math.min(
                          (merchant.current_transaction_volume /
                            merchant.avg_hourly_transaction_volume) *
                            100,
                          100,
                        )}%`,
                        backgroundColor:
                          merchant.current_transaction_volume <
                          merchant.rules.trigger_volume_threshold
                            ? "hsl(var(--destructive))"
                            : "hsl(var(--secondary))",
                      }}
                    />
                  </div>
                  <p className="mt-1.5 text-xs text-muted-foreground">
                    Offer triggers at &lt; {merchant.rules.trigger_volume_threshold} tx/h
                  </p>
                </div>
                <div className="shrink-0 rounded-2xl border border-wallet-line bg-muted/40 px-3 py-2 text-center">
                  <Clock className="mx-auto h-4 w-4 text-muted-foreground" />
                  <p className="mt-0.5 text-[10px] text-muted-foreground">Payone feed</p>
                </div>
              </div>
            </div>
          )}

          {/* ── Two-column: rules + breakdown ── */}
          <div className="grid gap-6 lg:grid-cols-[380px_1fr]">
            {merchant && <RuleEditor merchant={merchant} />}

            <div className="space-y-6">
              {stats && <ScenarioBreakdown data={stats.per_scenario} />}

              {/* Recent offers log */}
              <div className="rounded-[2rem] border border-wallet-line bg-card overflow-hidden">
                <div className="px-5 py-4 border-b border-wallet-line">
                  <div className="flex items-center gap-2">
                    <BadgePercent className="h-4 w-4 text-muted-foreground" />
                    <h2 className="text-sm font-bold text-foreground">Recent offers</h2>
                    <span className="ml-auto text-xs text-muted-foreground">Simulated log</span>
                  </div>
                </div>
                <div className="divide-y divide-wallet-line text-sm">
                  {[
                    { time: "10:42", scenario: "SHELTER_SEEKER", discount: "Free size upgrade", status: "redeemed" },
                    { time: "10:18", scenario: "COZY_WEATHER", discount: "15% off warm drinks", status: "redeemed" },
                    { time: "09:55", scenario: "NORMAL_CITY_FLOW", discount: "10% off next visit", status: "dismissed" },
                    { time: "09:30", scenario: "FESTIVAL_VIBE", discount: "20% off today only", status: "redeemed" },
                    { time: "09:07", scenario: "SHELTER_SEEKER", discount: "Free size upgrade", status: "pending" },
                  ].map((row, i) => (
                    <div
                      key={i}
                      className="grid grid-cols-[40px_1fr_auto_auto] items-center gap-3 px-5 py-3"
                    >
                      <span className="text-xs tabular-nums text-muted-foreground">{row.time}</span>
                      <div>
                        <span
                          className={`text-xs font-semibold ${
                            SCENARIO_LABELS[row.scenario]?.color ?? "text-foreground"
                          }`}
                        >
                          {SCENARIO_LABELS[row.scenario]?.label ?? row.scenario}
                        </span>
                        <p className="text-xs text-muted-foreground">{row.discount}</p>
                      </div>
                      <span
                        className={`rounded-full px-2 py-0.5 text-[10px] font-bold ${
                          row.status === "redeemed"
                            ? "bg-green-500/15 text-green-400"
                            : row.status === "dismissed"
                            ? "bg-destructive/15 text-destructive"
                            : "bg-muted text-muted-foreground"
                        }`}
                      >
                        {row.status === "redeemed" && <CheckCircle2 className="inline h-3 w-3 mr-0.5" />}
                        {row.status === "dismissed" && <X className="inline h-3 w-3 mr-0.5" />}
                        {row.status}
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </div>
        </div>
      )}
    </main>
  );
};

export default Merchant;
