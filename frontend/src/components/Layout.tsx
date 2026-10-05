import { Outlet, Link, useLocation } from "react-router-dom";
import styles from "./Layout.module.css";

export function Layout() {
  const location = useLocation();

  return (
    <div className={styles.layout}>
      <header className={styles.header}>
        <div className={styles.headerContent}>
          <Link to="/" className={styles.logo} aria-label="SafePayout Home">
            <span className={styles.logoIcon} aria-hidden="true">🛡️</span>
            <span className={styles.logoText}>SafePayout</span>
          </Link>
          <nav className={styles.nav} aria-label="Main navigation">
            <Link to="/" className={`${styles.navLink} ${location.pathname === "/" ? styles.active : ""}`}>
              New Run
            </Link>
          </nav>
        </div>
        <div className={styles.principle} role="status" aria-live="polite">
          AI proposes. Rules enforce. You approve. PayPal sends.
        </div>
      </header>
      <main className={styles.main} role="main">
        <Outlet />
      </main>
      <footer className={styles.footer}>
        <p>Built for "Build What's Next with PayPal and AI" hackathon</p>
      </footer>
    </div>
  );
}