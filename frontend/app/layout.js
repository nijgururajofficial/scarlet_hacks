import "./globals.css";

export const metadata = {
  title: "Day1 Brain",
  description: "A simple Next.js frontend for the Day1 Brain onboarding assistant.",
};

export default function RootLayout({ children }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
