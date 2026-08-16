import { Link, Outlet } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";

const menuItems = [
  { path: "/interne/HomePage", label: "Supervision" },
  { path: "/externe/HomePage", label: "Espace externe" },
  { path: "/ia", label: "IA" },
  { path: "/", label: "Accueil" },
];

export default function LayoutInterne() {
  const { user, logout } = useAuth();
  return (
    <div className="internal-shell">
      <aside className="internal-sidebar">
        <div className="internal-brand">
          <h2>ObRail</h2>
          <p>Espace interne</p>
        </div>

        <nav className="internal-nav" aria-label="Navigation interne">
          {menuItems.map((item) => (
            <Link key={item.path} to={item.path}>
              {item.label}
            </Link>
          ))}
        </nav>
        <div className="internal-nav">
          <span>{user?.email}</span>
          <small>Administrateur</small>
          <button type="button" onClick={logout}>Déconnexion</button>
        </div>
      </aside>

      <section className="internal-content">
        <Outlet />
      </section>
    </div>
  );
}
