import { listMerchants } from "@/lib/api";
import Link from "next/link";

export const revalidate = 0;

export default async function HomePage() {
  const merchants = await listMerchants();

  return (
    <main className="max-w-4xl mx-auto px-6 py-12">
      {/* Header */}
      <div className="mb-10">
        <p className="text-indigo-400 text-sm font-semibold tracking-widest uppercase mb-1">
          DSV Gruppe · Generative City-Wallet
        </p>
        <h1 className="text-4xl font-black text-white mb-2">
          Merchant Dashboard
        </h1>
        <p className="text-gray-400">
          Live Payone activity, AI-generated offers, and redemption tracking.
        </p>
      </div>

      {/* Merchant cards */}
      <div className="grid gap-5">
        {merchants.map((m) => {
          const ratio = m.current_transaction_volume / m.avg_hourly_transaction_volume;
          const isQuiet = m.current_transaction_volume < m.rules.trigger_volume_threshold;

          return (
            <Link
              key={m.id}
              href={`/merchant/${m.id}`}
              className="block bg-[#13132a] border border-[#2a2a45] rounded-2xl p-6 hover:border-indigo-500 transition-colors"
            >
              <div className="flex items-start justify-between gap-4">
                <div>
                  <h2 className="text-xl font-bold text-white mb-1">{m.name}</h2>
                  <p className="text-gray-500 text-sm">{m.address}</p>
                  <p className="text-gray-600 text-xs mt-1 capitalize">{m.category}</p>
                </div>

                <div className="text-right shrink-0">
                  <div
                    className={`inline-flex items-center gap-1.5 rounded-full px-3 py-1 text-xs font-semibold mb-2 ${
                      isQuiet
                        ? "bg-amber-500/15 text-amber-400 border border-amber-500/30"
                        : "bg-green-500/15 text-green-400 border border-green-500/30"
                    }`}
                  >
                    <span
                      className={`w-1.5 h-1.5 rounded-full ${
                        isQuiet ? "bg-amber-400" : "bg-green-400"
                      }`}
                    />
                    {isQuiet ? "Quiet — offer trigger active" : "Normal traffic"}
                  </div>
                  <p className="text-gray-400 text-sm">
                    {m.current_transaction_volume} /{" "}
                    {m.avg_hourly_transaction_volume} txns/hr
                  </p>
                  <div className="mt-2 h-2 w-32 bg-[#2a2a45] rounded-full ml-auto">
                    <div
                      className="h-2 rounded-full transition-all"
                      style={{
                        width: `${Math.min(ratio * 100, 100)}%`,
                        backgroundColor: isQuiet ? "#f59e0b" : "#22c55e",
                      }}
                    />
                  </div>
                </div>
              </div>
            </Link>
          );
        })}
      </div>
    </main>
  );
}
