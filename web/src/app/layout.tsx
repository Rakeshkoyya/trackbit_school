import type { Metadata, Viewport } from "next";
import { Geist, Geist_Mono } from "next/font/google";

import { AppProviders } from "@/providers/app-providers";
import "./globals.css";

const geistSans = Geist({ variable: "--font-geist-sans", subsets: ["latin"] });
const geistMono = Geist_Mono({ variable: "--font-geist-mono", subsets: ["latin"] });

// Runs before paint so the saved/system theme is applied with no flash of the
// wrong colors. Kept in sync with theme-toggle.tsx (STORAGE_KEY = trackbit_theme).
const themeInitScript = `(function(){try{var t=localStorage.getItem('trackbit_theme');if(t!=='light'&&t!=='dark'){t=window.matchMedia('(prefers-color-scheme: dark)').matches?'dark':'light';}var r=document.documentElement;r.classList.toggle('dark',t==='dark');r.style.colorScheme=t;}catch(e){}})();`;

export const metadata: Metadata = {
  title: "TrackBit — simple, stress-free task management",
  description:
    "Anyone can create boards and tasks, assign work to anyone, and everyone sees what's done. Built for small teams.",
  manifest: "/manifest.webmanifest",
  appleWebApp: { capable: true, title: "TrackBit", statusBarStyle: "default" },
  icons: { icon: "/icon.svg", apple: "/icon.svg" },
};

export const viewport: Viewport = {
  themeColor: "#2f6f4f",
  width: "device-width",
  initialScale: 1,
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en" className={`${geistSans.variable} ${geistMono.variable} h-full`} suppressHydrationWarning>
      <body className="min-h-dvh">
        <script dangerouslySetInnerHTML={{ __html: themeInitScript }} />
        <AppProviders>{children}</AppProviders>
      </body>
    </html>
  );
}
