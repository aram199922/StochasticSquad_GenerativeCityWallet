import { useMemo, useState } from "react";
import {
  BadgePercent,
  Bike,
  Building2,
  Coffee,
  LandPlot,
  MapPin,
  QrCode,
  Sparkles,
  Ticket,
  Train,
  WalletCards,
} from "lucide-react";
import type { CSSProperties } from "react";

type OfferTone = "premium" | "fresh" | "civic" | "night";

type DynamicOffer = {
  headline: string;
  description: string;
  discount_value: string;
  tone: OfferTone;
  ui_styling: {
    primary_color: string;
    background_gradient: string;
    icon_name: keyof typeof iconRegistry;
  };
};

const iconRegistry = {
  ticket: Ticket,
  train: Train,
  coffee: Coffee,
  bike: Bike,
  landmark: LandPlot,
  city: Building2,
  wallet: WalletCards,
  percent: BadgePercent,
};

const cityOffer: DynamicOffer = {
  headline: "Museum Mile Evening Pass",
  description: "Unlock late entry, metro transfer credit, and a neighborhood café reward for tonight’s cultural route.",
  discount_value: "32%",
  tone: "premium",
  ui_styling: {
    primary_color: "hsl(176 62% 52%)",
    background_gradient: "linear-gradient(145deg, hsl(224 34% 7%) 0%, hsl(221 47% 16%) 48%, hsl(176 54% 28%) 100%)",
    icon_name: "landmark",
  },
};

const companionOffers = [
  { label: "Transit", value: "$8 credit", icon: Train },
  { label: "Coffee", value: "2-for-1", icon: Coffee },
  { label: "Bike dock", value: "45 min", icon: Bike },
];

function DynamicOfferWidget({ offer }: { offer: DynamicOffer }) {
  const [claimed, setClaimed] = useState(false);
  const OfferIcon = iconRegistry[offer.ui_styling.icon_name] ?? Sparkles;

  const offerStyle = useMemo(
    () =>
      ({
        "--offer-primary": offer.ui_styling.primary_color,
        "--offer-gradient": offer.ui_styling.background_gradient,
      }) as CSSProperties,
    [offer.ui_styling.background_gradient, offer.ui_styling.primary_color],
  );

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
        <div className="flex items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <div className="grid h-12 w-12 place-items-center rounded-2xl bg-primary-foreground/12 ring-1 ring-primary-foreground/18 backdrop-blur">
              <OfferIcon className="h-6 w-6" aria-hidden="true" />
            </div>
            <div>
              <p className="text-sm font-semibold uppercase tracking-[0.18em] text-primary-foreground/68">City-Wallet</p>
              <p className="text-sm text-primary-foreground/72">Live offer · {offer.tone}</p>
            </div>
          </div>
          <WalletCards className="h-7 w-7 text-primary-foreground/75" aria-hidden="true" />
        </div>

        <div className="space-y-5">
          <div className="inline-flex items-center gap-2 rounded-full bg-primary-foreground/12 px-3 py-1.5 text-sm font-semibold text-primary-foreground ring-1 ring-primary-foreground/16 backdrop-blur">
            <Sparkles className="h-4 w-4" aria-hidden="true" />
            Generative route reward
          </div>
          <div className="max-w-xl space-y-4">
            <h1 className="font-display text-4xl font-black leading-[0.98] tracking-normal text-primary-foreground sm:text-6xl">
              {offer.headline}
            </h1>
            <p className="text-base leading-7 text-primary-foreground/76 sm:text-lg">{offer.description}</p>
          </div>
        </div>

        <div className="grid gap-4 lg:grid-cols-[1fr_220px] lg:items-end">
          <div className="rounded-[1.5rem] bg-primary-foreground/10 p-4 ring-1 ring-primary-foreground/16 backdrop-blur-xl">
            <div className="flex items-end justify-between gap-4">
              <div>
                <p className="text-sm text-primary-foreground/68">Instant value</p>
                <p className="text-6xl font-black leading-none text-primary-foreground sm:text-7xl">{offer.discount_value}</p>
              </div>
              <button
                type="button"
                onClick={() => setClaimed(true)}
                className="group inline-flex min-h-12 items-center justify-center gap-2 rounded-full bg-primary-foreground px-5 py-3 text-sm font-extrabold text-wallet-ink shadow-lg shadow-wallet-ink/20 transition-all duration-300 hover:scale-[1.03] hover:shadow-xl active:scale-[0.98]"
              >
                <QrCode className="h-4 w-4 transition-transform duration-300 group-hover:rotate-12" aria-hidden="true" />
                Claim Offer
              </button>
            </div>
          </div>

          {claimed ? (
            <div className="animate-qr-rise rounded-[1.5rem] bg-primary-foreground p-4 text-wallet-ink shadow-2xl shadow-wallet-ink/30">
              <div className="grid aspect-square place-items-center rounded-2xl bg-[linear-gradient(135deg,hsl(var(--muted)),hsl(var(--card)))] p-3">
                <div className="grid h-full w-full grid-cols-5 grid-rows-5 gap-1">
                  {Array.from({ length: 25 }).map((_, index) => (
                    <span
                      key={index}
                      className={`rounded-[0.28rem] ${[0, 1, 3, 5, 6, 7, 10, 12, 14, 17, 18, 19, 21, 23, 24].includes(index) ? "bg-wallet-ink" : "bg-transparent"}`}
                    />
                  ))}
                </div>
              </div>
              <p className="mt-3 text-center text-xs font-bold uppercase tracking-[0.18em] text-muted-foreground">Scan to redeem</p>
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

const Index = () => {
  return (
    <main className="min-h-screen px-4 py-5 sm:px-6 lg:px-10">
      <div className="mx-auto grid max-w-7xl gap-6 lg:grid-cols-[minmax(0,1fr)_380px] lg:items-center">
        <DynamicOfferWidget offer={cityOffer} />

        <aside className="space-y-5">
          <div className="glass-panel soft-shadow rounded-[2rem] border border-wallet-line p-5">
            <div className="mb-5 flex items-center justify-between">
              <div>
                <p className="text-sm font-bold uppercase tracking-[0.16em] text-muted-foreground">Wallet pulse</p>
                <h2 className="mt-1 text-2xl font-black tracking-normal text-foreground">Generated for your city path</h2>
              </div>
              <div className="grid h-11 w-11 place-items-center rounded-2xl bg-secondary text-secondary-foreground animate-float-soft">
                <MapPin className="h-5 w-5" aria-hidden="true" />
              </div>
            </div>
            <div className="space-y-3">
              {companionOffers.map((item) => {
                const Icon = item.icon;
                return (
                  <div key={item.label} className="flex items-center justify-between rounded-2xl border border-wallet-line bg-card/70 p-4 transition-all duration-300 hover:-translate-y-0.5 hover:bg-card">
                    <div className="flex items-center gap-3">
                      <div className="grid h-10 w-10 place-items-center rounded-xl bg-muted text-foreground">
                        <Icon className="h-5 w-5" aria-hidden="true" />
                      </div>
                      <span className="font-bold text-foreground">{item.label}</span>
                    </div>
                    <span className="text-sm font-extrabold text-secondary">{item.value}</span>
                  </div>
                );
              })}
            </div>
          </div>

          <div className="rounded-[2rem] border border-wallet-line bg-wallet-ink p-5 text-primary-foreground soft-shadow">
            <p className="text-sm font-semibold text-primary-foreground/62">JSON-controlled styling</p>
            <pre className="mt-3 overflow-x-auto rounded-2xl bg-primary-foreground/8 p-4 text-xs leading-6 text-primary-foreground/78">
{`{
  "headline": "${cityOffer.headline}",
  "discount_value": "${cityOffer.discount_value}",
  "ui_styling": {
    "primary_color": "${cityOffer.ui_styling.primary_color}",
    "icon_name": "${cityOffer.ui_styling.icon_name}"
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
