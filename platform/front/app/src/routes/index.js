// fichier : platform/front/app/src/routes/index.js

import { Routes, Route, Navigate } from 'react-router-dom';
import ProtectedRoute from '../auth/ProtectedRoute';

// IMPORT DES LAYOUTS
import LayoutExterne from '../layouts/LayoutExterne';
import LayoutInterne from '../layouts/LayoutInterne';

// IMPORT Page d'accueil
import HomePage from '../pages/HomePage';
import LoginPage from '../pages/auth/LoginPage';
import RegisterPage from '../pages/auth/RegisterPage';
import LegalPage from '../pages/legal/LegalPage';

// IMPORT DES PAGES EXTERNES (partenaire)
import ExterneHomePage from '../pages/externe/HomePage';
import MapPage from '../pages/externe/MapPage';
import TrainPage from '../pages/externe/TrajetsPage';
import StatisticsPage from '../pages/externe/StatisticsPage';
import OperatorsPage from '../pages/externe/OperatorsPage';

// IMPORT DES PAGES INTERNES (admin)
import InterneHomePage from '../pages/interne/HomePage';
import IaPage from '../pages/ia/IaPage';

export default function AppRoutes() {
  return (
    <Routes>
      {/* Page d'accueil */}
      <Route path="/" element={<HomePage />} />
      <Route path="/login" element={<LoginPage />} />
      <Route path="/register" element={<RegisterPage />} />
      <Route path="/legal" element={<LegalPage />} />

      <Route element={<ProtectedRoute />}>
        <Route path="/ia" element={<LayoutInterne />}>
          <Route index element={<IaPage />} />
        </Route>
        <Route path="/externe" element={<LayoutExterne />}>
          <Route index element={<ExterneHomePage />} />
          <Route path="HomePage" element={<ExterneHomePage />} />
          <Route path="Map" element={<MapPage />} />
          <Route path="Trajets" element={<TrainPage />} />
          <Route path="Statistique" element={<StatisticsPage />} />
          <Route path="Operateur" element={<OperatorsPage />} />
          <Route path="*" element={<Navigate to="/externe" replace />} />
        </Route>
      </Route>

      <Route element={<ProtectedRoute adminOnly />}>
        <Route path="/interne" element={<LayoutInterne />}>
          <Route index element={<InterneHomePage />} />
          <Route path="HomePage" element={<InterneHomePage />} />
          <Route path="IA" element={<Navigate to="/ia" replace />} />
          <Route path="*" element={<Navigate to="/interne" replace />} />
        </Route>
      </Route>

      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
