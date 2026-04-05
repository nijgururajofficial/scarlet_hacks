import "./globals.css";

// This metadata gives the browser tab a product-like title and description.
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
