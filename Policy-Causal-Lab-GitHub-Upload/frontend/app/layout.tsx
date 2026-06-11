import "./globals.css";

export const metadata = { title: "Policy Causal Lab", description: "Policy evaluation and causal inference workbench" };

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="zh-CN"><body>{children}</body></html>;
}
