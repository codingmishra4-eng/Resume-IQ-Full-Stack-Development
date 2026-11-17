import Link from "next/link";
export default function NotFound() {
  return (
    <main className="standalone">
      <span className="eyebrow">404 / PAGE NOT FOUND</span>
      <h1>This page took a different path.</h1>
      <p>Return to your workspace to keep moving.</p>
      <Link className="button primary" href="/dashboard">
        Open workspace
      </Link>
    </main>
  );
}
