import "../global.css";
import { Stack } from "expo-router";
import { StatusBar } from "expo-status-bar";

export default function RootLayout() {
  return (
    <>
      <StatusBar style="light" />
      <Stack
        screenOptions={{
          headerStyle: { backgroundColor: "#0f0f1a" },
          headerTintColor: "#fff",
          headerTitleStyle: { fontWeight: "700" },
          contentStyle: { backgroundColor: "#0f0f1a" },
        }}
      >
        <Stack.Screen name="index" options={{ title: "City Wallet" }} />
        <Stack.Screen name="offer" options={{ title: "Your Offer" }} />
        <Stack.Screen name="redeem" options={{ title: "Redeem" }} />
      </Stack>
    </>
  );
}
