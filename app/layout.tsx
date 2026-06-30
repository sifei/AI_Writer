import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Biomedical Submission Assistant",
  description: "Journal-fit analysis and guided revision for biomedical manuscripts."
};

export default function RootLayout({
  children
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
