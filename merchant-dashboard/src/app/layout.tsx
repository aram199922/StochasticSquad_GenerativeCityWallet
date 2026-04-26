import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "City Wallet — Merchant Dashboard",
  description: "DSV Gruppe | Generative City-Wallet merchant portal",
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body className="bg-[#0a0a14] text-white min-h-screen">{children}</body>
    </html>
  );
}
