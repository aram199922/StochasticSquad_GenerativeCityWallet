/**
 * Redemption screen — Seamless Checkout (Module 03).
 * Shows a dynamic QR code encoding the discount_code.
 * Tapping "Confirm Redemption" simulates the merchant scanning it.
 */
import { useLocalSearchParams, useRouter } from "expo-router";
import { useMemo, useState } from "react";
import {
  ActivityIndicator,
  Text,
  TouchableOpacity,
  View,
} from "react-native";
import QRCode from "react-native-qrcode-svg";
import type { GenUICard, RedeemResponse } from "../lib/api";
import { redeemOffer } from "../lib/api";

type Phase = "pending" | "loading" | "success" | "failed";

export default function RedeemScreen() {
  const router = useRouter();
  const params = useLocalSearchParams<{ card: string }>();
  const [phase, setPhase] = useState<Phase>("pending");
  const [result, setResult] = useState<RedeemResponse | null>(null);

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
        <Text className="text-white text-lg">No offer data.</Text>
        <TouchableOpacity onPress={() => router.back()} className="mt-4">
          <Text className="text-indigo-400">Go back</Text>
        </TouchableOpacity>
      </View>
    );
  }

  async function handleRedeem() {
    if (!card) return;
    setPhase("loading");
    try {
      const res = await redeemOffer(card.discount_code, card.merchant_id);
      setResult(res);
      setPhase(res.success ? "success" : "failed");
    } catch {
      setResult({ success: false, message: "Network error — could not reach server." });
      setPhase("failed");
    }
  }

  // QR payload: encode offer details as JSON string for the merchant scanner
  const qrPayload = JSON.stringify({
    code: card.discount_code,
    merchant: card.merchant_id,
    discount: card.discount_percent,
    expiry: card.expiry_iso,
  });

  return (
    <View className="flex-1 bg-[#0f0f1a] px-7 pt-10">
      {/* Merchant & headline */}
      <Text className="text-gray-400 text-sm mb-1">{card.merchant_name}</Text>
      <Text className="text-white text-2xl font-black mb-6">{card.headline}</Text>

      {/* QR code */}
      {phase !== "success" && (
        <View className="bg-white rounded-3xl p-6 items-center mb-6 self-center">
          <QRCode
            value={qrPayload}
            size={220}
            color="#0f0f1a"
            backgroundColor="white"
          />
          <Text className="text-gray-500 text-xs mt-3 font-mono">
            {card.discount_code}
          </Text>
        </View>
      )}

      {/* Discount badge */}
      {phase !== "success" && (
        <View
          className="self-center rounded-full px-6 py-2 mb-8"
          style={{ backgroundColor: card.color_hex }}
        >
          <Text className="text-white text-xl font-black">
            {card.discount_percent}% OFF
          </Text>
        </View>
      )}

      {/* State-driven bottom section */}
      {phase === "pending" && (
        <>
          <Text className="text-gray-500 text-sm text-center mb-5">
            Show this QR code to the cashier at {card.merchant_name}.
          </Text>
          <TouchableOpacity
            onPress={handleRedeem}
            className="rounded-2xl py-5 items-center"
            style={{ backgroundColor: card.color_hex }}
          >
            <Text className="text-white text-lg font-bold">
              Confirm Redemption
            </Text>
            <Text className="text-white/70 text-xs mt-1">
              (Simulates merchant scan)
            </Text>
          </TouchableOpacity>
        </>
      )}

      {phase === "loading" && (
        <View className="items-center py-6">
          <ActivityIndicator size="large" color="#6366f1" />
          <Text className="text-gray-400 mt-3 text-sm">Validating with merchant...</Text>
        </View>
      )}

      {phase === "success" && (
        <View className="items-center py-6">
          <View className="bg-green-500/10 border border-green-500 rounded-3xl p-8 items-center mb-6 w-full">
            <Text className="text-6xl mb-3">✓</Text>
            <Text className="text-green-400 text-2xl font-black mb-2">Redeemed!</Text>
            <Text className="text-gray-400 text-sm text-center">
              Your {card.discount_percent}% discount has been applied.
            </Text>
            {result?.redeemed_at && (
              <Text className="text-gray-600 text-xs mt-3">
                {new Date(result.redeemed_at).toLocaleTimeString()}
              </Text>
            )}
          </View>
          <TouchableOpacity
            onPress={() => router.push("/")}
            className="bg-indigo-600 rounded-2xl py-4 px-8 items-center"
          >
            <Text className="text-white font-bold text-base">Back to City Wallet</Text>
          </TouchableOpacity>
        </View>
      )}

      {phase === "failed" && (
        <View className="bg-red-900/30 border border-red-700 rounded-2xl p-5 mb-4">
          <Text className="text-red-300 font-semibold mb-1">Redemption failed</Text>
          <Text className="text-red-400 text-sm">{result?.message}</Text>
          <TouchableOpacity
            onPress={() => setPhase("pending")}
            className="mt-3 bg-red-700 rounded-xl py-2 items-center"
          >
            <Text className="text-white text-sm font-semibold">Try again</Text>
          </TouchableOpacity>
        </View>
      )}
    </View>
  );
}
