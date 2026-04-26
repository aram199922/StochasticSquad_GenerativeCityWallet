/**
 * Offer Card screen — Generative Offer Engine output (Module 02).
 * Designed to comply with the 3-Second Rule: headline, discount, one CTA.
 * Background colour is driven by the GenUI payload's color_hex.
 */
import { useLocalSearchParams, useRouter } from "expo-router";
import { useMemo } from "react";
import {
  ScrollView,
  Text,
  TouchableOpacity,
  View,
} from "react-native";
import type { GenUICard } from "../lib/api";

function hexToRgb(hex: string): string {
  const r = parseInt(hex.slice(1, 3), 16);
  const g = parseInt(hex.slice(3, 5), 16);
  const b = parseInt(hex.slice(5, 7), 16);
  return `${r}, ${g}, ${b}`;
}

function framingEmoji(framing: string): string {
  const map: Record<string, string> = {
    warm_shelter: "☕",
    scarcity_urgency: "⚡",
    celebration: "🎉",
    convenience: "✨",
    discovery: "🗺",
  };
  return map[framing] ?? "🎁";
}

function timeUntilExpiry(isoString: string): string {
  const diff = new Date(isoString).getTime() - Date.now();
  if (diff <= 0) return "Expired";
  const mins = Math.floor(diff / 60000);
  return `${mins} min left`;
}

export default function OfferScreen() {
  const router = useRouter();
  const params = useLocalSearchParams<{ card: string }>();

  const card: GenUICard | null = useMemo(() => {
    try {
      return params.card ? JSON.parse(params.card) : null;
    } catch {
      return null;
    }
  }, [params.card]);

  if (!card) {
    return (
      <View className="flex-1 bg-[#0f0f1a] items-center justify-center px-8">
        <Text className="text-white text-lg">No offer data found.</Text>
        <TouchableOpacity onPress={() => router.back()} className="mt-4">
          <Text className="text-indigo-400">Go back</Text>
        </TouchableOpacity>
      </View>
    );
  }

  const rgb = hexToRgb(card.color_hex);
  const emoji = framingEmoji(card.emotional_framing);
  const expiry = timeUntilExpiry(card.expiry_iso);

  return (
    <ScrollView
      className="flex-1 bg-[#0f0f1a]"
      contentContainerStyle={{ padding: 0, flexGrow: 1 }}
    >
      {/* Hero card — the 3-second zone */}
      <View
        style={{ backgroundColor: card.color_hex }}
        className="px-7 pt-14 pb-10"
      >
        <Text className="text-white/70 text-sm font-medium mb-2">
          {card.merchant_name}
        </Text>

        {/* Headline — must be understood in 3 seconds */}
        <Text className="text-white text-4xl font-black leading-tight mb-4">
          {emoji} {card.headline}
        </Text>

        {/* Discount badge */}
        <View className="flex-row items-center gap-3 mb-5">
          <View
            className="rounded-full px-5 py-2"
            style={{ backgroundColor: `rgba(0,0,0,0.25)` }}
          >
            <Text className="text-white text-2xl font-black">
              {card.discount_percent}% OFF
            </Text>
          </View>
          <View
            className="rounded-full px-3 py-2"
            style={{ backgroundColor: `rgba(0,0,0,0.15)` }}
          >
            <Text className="text-white/80 text-sm font-semibold">
              ⏱ {expiry}
            </Text>
          </View>
        </View>

        <Text className="text-white/80 text-base">{card.subline}</Text>
      </View>

      {/* Offer details */}
      <View className="px-7 py-6">
        <View className="bg-[#1e1e30] rounded-2xl p-5 mb-5">
          <Text className="text-gray-400 text-xs uppercase tracking-widest mb-3">
            Offer Details
          </Text>
          <DetailRow label="Discount code" value={card.discount_code} mono />
          <DetailRow label="Framing" value={card.emotional_framing} />
          <DetailRow label="Matched intent" value={card.intent_matched} />
          <DetailRow
            label="Expires"
            value={new Date(card.expiry_iso).toLocaleTimeString([], {
              hour: "2-digit",
              minute: "2-digit",
            })}
          />
        </View>

        {/* CTA */}
        <TouchableOpacity
          onPress={() =>
            router.push({
              pathname: "/redeem",
              params: { card: JSON.stringify(card) },
            })
          }
          className="rounded-2xl py-5 items-center"
          style={{ backgroundColor: card.color_hex }}
        >
          <Text className="text-white text-xl font-black">Claim Offer →</Text>
          <Text className="text-white/70 text-sm mt-1">
            Show QR code at {card.merchant_name}
          </Text>
        </TouchableOpacity>

        <TouchableOpacity onPress={() => router.back()} className="mt-4 items-center">
          <Text className="text-gray-600 text-sm">Dismiss offer</Text>
        </TouchableOpacity>
      </View>
    </ScrollView>
  );
}

function DetailRow({
  label,
  value,
  mono,
}: {
  label: string;
  value: string;
  mono?: boolean;
}) {
  return (
    <View className="flex-row justify-between items-center py-2 border-b border-[#2a2a45]">
      <Text className="text-gray-500 text-sm">{label}</Text>
      <Text
        className={`text-sm font-semibold text-gray-200 ${mono ? "font-mono" : ""}`}
      >
        {value}
      </Text>
    </View>
  );
}
