import type { Metadata } from "next";
import "./globals.css";
import { Providers } from "./providers";

export const metadata: Metadata = {
  title: "CEO Dashboard — Detección de Ganancias Sobrenormales",
  description: "Sistema de análisis Core+Catalyst para NYSE/Nasdaq",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="es">
      <body>
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
