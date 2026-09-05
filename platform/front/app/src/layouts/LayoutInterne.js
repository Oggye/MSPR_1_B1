import { NavLink, Outlet, useLocation } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";
import "../pages/interne/HomePage.css";

const menuItems = [
  { path: "/interne/HomePage", label: "Supervision", adminOnly: true },
  { path: "/externe/HomePage", label: "Espace externe" },
  { path: "/ia", label: "IA" },
  { path: "/", label: "Accueil" },
];

export default function LayoutInterne() {
  const { user, logout } = useAuth();
  const location = useLocation();
  const isIa = location.pathname === "/ia";
  const visibleMenuItems = menuItems.filter(
    (item) => !item.adminOnly || user?.role === "admin"
  );

  return (
    <div className="internal-shell">
      <aside className="internal-sidebar">
        <div className="internal-brand">
          <h2>ObRail</h2>
          <p>{isIa ? "Espace IA" : "Espace interne"}</p>
        </div>

        <nav
          className="internal-nav"
          aria-label={isIa ? "Navigation IA" : "Navigation interne"}
        >
          {visibleMenuItems.map((item) => (
            <NavLink
              key={item.path}
              to={item.path}
              end
              className={({ isActive }) => (
                isActive
                || (item.path === "/interne/HomePage"
                  && location.pathname === "/interne")
                  ? "active"
                  : undefined
              )}
            >
              {item.label}
            </NavLink>
          ))}
        </nav>
        <div className="internal-nav">
          <span>{user?.email}</span>
          <small>
            {user?.role === "admin" ? "Administrateur" : "Utilisateur"}
          </small>
          <button type="button" onClick={logout}>Déconnexion</button>
        </div>
      </aside>

      <section className="internal-content">
        <Outlet />
      </section>
    </div>
  );
}
