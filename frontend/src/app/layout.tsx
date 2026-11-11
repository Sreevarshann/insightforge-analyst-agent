import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import Script from "next/script";
import { Providers } from "@/components/Providers";
import { themeInitScript } from "@/components/theme";
import "./globals.css";

const sans = Geist({ variable: "--font-geist-sans", subsets: ["latin"] });
const mono = Geist_Mono({ variable: "--font-geist-mono", subsets: ["latin"] });

export const metadata: Metadata = {
  title: { default: "InsightForge", template: "%s · InsightForge" },
  description: "From data to decisions, with every number explained.",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en" data-theme="dark" suppressHydrationWarning className={`${sans.variable} ${mono.variable}`}>
      <body className="min-h-dvh antialiased">
        <Script id="theme-init" strategy="beforeInteractive">{themeInitScript}</Script>
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
