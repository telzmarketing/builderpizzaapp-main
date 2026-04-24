/**
 * AdminGuard — redireciona para /painel/login se não houver token JWT válido.
 * Envolva todas as rotas /painel/* com este componente.
 */
import { Navigate, Outlet } from "react-router-dom";

export default function AdminGuard() {
  const token = localStorage.getItem("admin_token");
  if (!token) return <Navigate to="/painel/login" replace />;
  return (
    <div className="admin-panel">
      <Outlet />
    </div>
  );
}
