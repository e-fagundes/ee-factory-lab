import "./styles.css";
import type { ReactNode } from "react";

export const metadata = {
  title: "EE Factory Lab",
  description: "IDP-style Ansible Execution Environment factory"
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
