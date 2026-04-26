import { getMerchantActivity, OfferRecord, RedemptionRecord } from "@/lib/api";
import Link from "next/link";

export const revalidate = 0;

function framingColor(framing: string): string {
  const map: Record<string, string> = {
    warm_shelter: "text-amber-400 bg-amber-500/10 border-amber-500/30",
    scarcity_urgency: "text-red-400 bg-red-500/10 border-red-500/30",
    celebration: "text-purple-400 bg-purple-500/10 border-purple-500/30",
    convenience: "text-blue-400 bg-blue-500/10 border-blue-500/30",
    discovery: "text-teal-400 bg-teal-500/10 border-teal-500/30",
  };
  return map[framing] ?? "text-gray-400 bg-gray-500/10 border-gray-500/30";
}

function timeAgo(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins}m ago`;
  return `${Math.floor(mins / 60)}h ago`;
}

export default async function MerchantPage({
  params,
}: {
  params: { id: string };
}) {
  const activity = await getMerchantActivity(params.id);
  const ratio = activity.payone_volume_ratio;

  return (
    <main className="max-w-4xl mx-auto px-6 py-12">
      {/* Back link */}
      <Link
        href="/"
        className="text-gray-500 hover:text-white text-sm mb-6 inline-flex items-center gap-1 transition-colors"
      >
        ← All merchants
      </Link>

      {/* Header */}
      <div className="mb-8">
        <h1 className="text-3xl font-black text-white mb-1">
          {activity.merchant_name}
        </h1>
        <p className="text-gray-500 text-sm">{params.id}</p>
      </div>

      {/* KPI row */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 mb-8">
        <KpiCard
          label="Current txns/hr"
          value={String(activity.current_transactions)}
          sub={`avg ${activity.avg_transactions}`}
          highlight={activity.trigger_active}
        />
        <KpiCard
          label="Volume ratio"
          value={`${(ratio * 100).toFixed(0)}%`}
          sub={activity.trigger_active ? "Below threshold" : "Normal"}
          highlight={activity.trigger_active}
        />
        <KpiCard
          label="Offers generated"
          value={String(activity.offers_generated)}
          sub="this session"
        />
        <KpiCard
          label="Redemptions"
          value={String(activity.redemptions_count)}
          sub={`of ${activity.offers_generated} offers`}
          positive
        />
      </div>

      {/* Volume gauge */}
      <div className="bg-[#13132a] border border-[#2a2a45] rounded-2xl p-5 mb-8">
        <div className="flex justify-between items-center mb-3">
          <p className="text-gray-400 text-sm uppercase tracking-widest text-xs">
            Payone Transaction Volume
          </p>
          <span
            className={`text-xs font-semibold px-2 py-0.5 rounded-full ${
              activity.trigger_active
                ? "bg-amber-500/15 text-amber-400"
                : "bg-green-500/15 text-green-400"
            }`}
          >
            {activity.trigger_active ? "Offer trigger ACTIVE" : "Normal traffic"}
          </span>
        </div>
        <div className="h-4 bg-[#2a2a45] rounded-full overflow-hidden">
          <div
            className="h-4 rounded-full transition-all duration-500"
            style={{
              width: `${Math.min(ratio * 100, 100)}%`,
              backgroundColor: activity.trigger_active ? "#f59e0b" : "#22c55e",
            }}
          />
        </div>
        <div className="flex justify-between mt-1">
          <span className="text-gray-600 text-xs">0</span>
          <span className="text-gray-600 text-xs">
            {activity.current_transactions} / {activity.avg_transactions} txns/hr
          </span>
        </div>
      </div>

      {/* Offer Log */}
      <Section title="Recent Offers" count={activity.offers_generated}>
        {activity.recent_offers.length === 0 ? (
          <EmptyState message="No offers generated yet." />
        ) : (
          [...activity.recent_offers].reverse().map((o) => (
            <OfferRow key={o.offer_id} offer={o} />
          ))
        )}
      </Section>

      {/* Redemption Log */}
      <Section title="Redemptions" count={activity.redemptions_count} className="mt-8">
        {activity.recent_redemptions.length === 0 ? (
          <EmptyState message="No redemptions yet." />
        ) : (
          [...activity.recent_redemptions].reverse().map((r) => (
            <RedemptionRow key={r.offer_id} redemption={r} />
          ))
        )}
      </Section>
    </main>
  );

  function OfferRow({ offer }: { offer: OfferRecord }) {
    return (
      <div className="flex items-center justify-between gap-4 py-3 border-b border-[#2a2a45] last:border-0">
        <div className="flex-1 min-w-0">
          <p className="text-white text-sm font-semibold truncate">{offer.headline}</p>
          <p className="text-gray-500 text-xs mt-0.5">{offer.subline}</p>
        </div>
        <div className="flex items-center gap-2 shrink-0">
          <span
            className={`text-xs font-semibold px-2 py-0.5 rounded-full border ${framingColor(offer.emotional_framing)}`}
          >
            {offer.emotional_framing}
          </span>
          <span className="text-gray-400 text-sm font-bold">
            {offer.discount_percent}%
          </span>
          <span
            className="w-2.5 h-2.5 rounded-full"
            style={{ backgroundColor: offer.color_hex }}
          />
        </div>
      </div>
    );
  }

  function RedemptionRow({ redemption }: { redemption: RedemptionRecord }) {
    return (
      <div className="flex items-center justify-between gap-4 py-3 border-b border-[#2a2a45] last:border-0">
        <div className="flex-1 min-w-0">
          <p className="text-white text-sm font-semibold truncate">
            {redemption.headline}
          </p>
          <p className="text-gray-500 text-xs font-mono mt-0.5">
            {redemption.discount_code}
          </p>
        </div>
        <div className="flex items-center gap-2 shrink-0">
          <span className="text-green-400 text-sm font-bold">
            -{redemption.discount_percent}%
          </span>
          <span className="text-gray-500 text-xs">
            {timeAgo(redemption.redeemed_at)}
          </span>
          <span className="text-green-400 text-lg">✓</span>
        </div>
      </div>
    );
  }
}

function KpiCard({
  label,
  value,
  sub,
  highlight,
  positive,
}: {
  label: string;
  value: string;
  sub: string;
  highlight?: boolean;
  positive?: boolean;
}) {
  return (
    <div className="bg-[#13132a] border border-[#2a2a45] rounded-2xl p-4">
      <p className="text-gray-500 text-xs uppercase tracking-widest mb-1">{label}</p>
      <p
        className={`text-3xl font-black mb-0.5 ${
          highlight ? "text-amber-400" : positive ? "text-green-400" : "text-white"
        }`}
      >
        {value}
      </p>
      <p className="text-gray-600 text-xs">{sub}</p>
    </div>
  );
}

function Section({
  title,
  count,
  children,
  className,
}: {
  title: string;
  count: number;
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <div className={`bg-[#13132a] border border-[#2a2a45] rounded-2xl p-5 ${className ?? ""}`}>
      <div className="flex items-center justify-between mb-4">
        <p className="text-gray-400 text-xs uppercase tracking-widest">{title}</p>
        <span className="text-xs font-semibold text-indigo-400 bg-indigo-500/10 border border-indigo-500/30 rounded-full px-2 py-0.5">
          {count} total
        </span>
      </div>
      {children}
    </div>
  );
}

function EmptyState({ message }: { message: string }) {
  return (
    <p className="text-gray-600 text-sm py-4 text-center">{message}</p>
  );
}
