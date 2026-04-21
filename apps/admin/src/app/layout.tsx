import type { Metadata } from "next";
import "./globals.css";
import "./design-tokens.css";
import { Providers } from "@/components/providers";
import { Toaster } from "sonner";

export const metadata: Metadata = {
  title: {
    template: "%s | NIA Admin",
    default: "NIA Admin Console",
  },
  description: "NIA Platform — Admin Console for managing AI assistants",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
  <html lang="en" className="theme-wine dark" suppressHydrationWarning>
      <body>
        <Providers>
          {children}
          <Toaster position="bottom-right" richColors expand />
        </Providers>
      </body>
    </html>
  );
}
