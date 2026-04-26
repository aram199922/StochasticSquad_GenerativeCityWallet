/**
 * Home screen — Context Sensing Layer (Module 01).
 * Simulates Mia's location near Stuttgart and shows live context signals.
 * On-device intent is inferred locally; only the abstract string goes to the backend.
 */
import { useRouter } from "expo-router";
import { useEffect, useState } from "react";
import {
  ActivityIndicator,
  ScrollView,
  Text,
  TouchableOpacity,
  View,
} from "react-native";
import {
  ContextState,
  fetchContext,
  generateOffer,
  GenUICard,
  inferIntent,
} from "../lib/api";

// Stuttgart old-town coordinates (Mia's simulated position)
const MIA_LAT = 48.7758;
const MIA_LON = 9.1829;
const MERCHANT_ID = "merchant_001"; // Café Müller — closest to Mia

type Phase = "idle" | "sensing" | "generating" | "ready" | "error";

export default function HomeScreen() {
  const router = useRouter();
  const [phase, setPhase] = useState<Phase>("idle");
  const [context, setContext] = useState<ContextState | null>(null);
  const [intent, setIntent] = useState<string>("");
  const [card, setCard] = useState<GenUICard | null>(null);
  const [error, setError] = useState<string>("");

  async function handleFindOffer() {
    try {
      setPhase("sensing");
      setError("");

      // Module 01: fetch context
      const ctx = await fetchContext(MERCHANT_ID, MIA_LAT, MIA_LON);
      setContext(ctx);

      // On-device intent inference (no raw coords go to backend)
      const userIntent = inferIntent(ctx);
      setIntent(userIntent);

      setPhase("generating");

      // Module 02: generate offer
      const offerCard = await generateOffer(MERCHANT_ID, userIntent, ctx);
      setCard(offerCard);
      setPhase("ready");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Unknown error");
      setPhase("error");
    }
  }

  function handleViewOffer() {
    if (!card) return;
    router.push({ pathname: "/offer", params: { card: JSON.stringify(card) } });
  }

  const tempIcon =
    context && context.temp_celsius < 14
      ? "🌥"
      : context
      ? "☀️"
      : "";

  return (
    <ScrollView
      className="flex-1 bg-[#0f0f1a]"
      contentContainerStyle={{ padding: 24, paddingBottom: 48 }}
    >
      {/* Header */}
      <View className="mb-8">
        <Text className="text-white text-3xl font-bold mb-1">City Wallet</Text>
        <Text className="text-gray-400 text-sm">
          Stuttgart Old Town · Simulated position
        </Text>
      </View>

      {/* Context signals card */}
      {context && (
        <View className="bg-[#1e1e30] rounded-2xl p-5 mb-6">
          <Text className="text-gray-400 text-xs uppercase tracking-widest mb-3">
            Context Signals
          </Text>

          <SignalRow
            label="Weather"
            value={`${tempIcon} ${context.weather_description}, ${context.temp_celsius.toFixed(1)}°C`}
          />
          <SignalRow
            label="Feels like"
            value={`${context.feels_like.toFixed(1)}°C`}
          />
          <SignalRow
            label="Nearby"
            value={context.merchant_name}
          />
          <SignalRow
            label="Merchant activity"
            value={`${context.current_transactions} / ${context.avg_transactions} txns/hr`}
            highlight={context.trigger_active}
          />
          {context.local_events.length > 0 && (
            <SignalRow
              label="Local events"
              value={context.local_events[0]}
            />
          )}
          {intent && (
            <View className="mt-3 pt-3 border-t border-[#2a2a45]">
              <Text className="text-gray-500 text-xs">
                On-device intent (never sent raw)
              </Text>
              <Text className="text-indigo-300 text-sm font-semibold mt-1">
                {intent}
              </Text>
            </View>
          )}
        </View>
      )}

      {/* CTA / status */}
      {phase === "idle" && (
        <TouchableOpacity
          onPress={handleFindOffer}
          className="bg-indigo-600 rounded-2xl py-5 items-center"
        >
          <Text className="text-white text-lg font-bold">Find Nearby Offers</Text>
          <Text className="text-indigo-300 text-xs mt-1">
            Sensing weather, events & merchant activity
          </Text>
        </TouchableOpacity>
      )}

      {(phase === "sensing" || phase === "generating") && (
        <View className="items-center py-10">
          <ActivityIndicator size="large" color="#6366f1" />
          <Text className="text-gray-400 mt-4 text-sm">
            {phase === "sensing"
              ? "Reading context signals..."
              : "Generating your personalised offer..."}
          </Text>
        </View>
      )}

      {phase === "ready" && card && (
        <TouchableOpacity
          onPress={handleViewOffer}
          className="rounded-2xl py-5 items-center"
          style={{ backgroundColor: card.color_hex }}
        >
          <Text className="text-white text-lg font-bold px-4 text-center">
            {card.headline}
          </Text>
          <Text className="text-white/80 text-sm mt-1">Tap to view offer →</Text>
        </TouchableOpacity>
      )}

      {phase === "error" && (
        <View className="bg-red-900/30 border border-red-700 rounded-2xl p-4">
          <Text className="text-red-300 font-semibold mb-1">Something went wrong</Text>
          <Text className="text-red-400 text-xs">{error}</Text>
          <TouchableOpacity
            onPress={() => setPhase("idle")}
            className="mt-3 bg-red-700 rounded-xl py-2 items-center"
          >
            <Text className="text-white text-sm font-semibold">Retry</Text>
          </TouchableOpacity>
        </View>
      )}

      {/* Privacy note */}
      <View className="mt-8 flex-row items-center">
        <Text className="text-gray-600 text-xs">
          🔒 Your location stays on device. Only abstract intents are shared.
        </Text>
      </View>
    </ScrollView>
  );
}

function SignalRow({
  label,
  value,
  highlight,
}: {
  label: string;
  value: string;
  highlight?: boolean;
}) {
  return (
    <View className="flex-row justify-between items-center py-2 border-b border-[#2a2a45]">
      <Text className="text-gray-500 text-sm">{label}</Text>
      <Text
        className={`text-sm font-medium ${
          highlight ? "text-amber-400" : "text-gray-200"
        }`}
      >
        {value}
      </Text>
    </View>
  );
}
