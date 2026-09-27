import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "AIRE — Autonomous Incident Response Engineer",
  description: "Watch an agent investigate and resolve simulated production incidents.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
