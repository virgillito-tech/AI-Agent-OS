import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "AI Agent OS",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="it" className="dark">
      <body className="bg-gray-900 text-gray-100 antialiased h-screen overflow-hidden">
        {children}
      </body>
    </html>
  );
}