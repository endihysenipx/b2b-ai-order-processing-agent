import { BrowserRouter, Navigate, Outlet, Route, Routes, useLocation } from "react-router-dom";

import { getAccessToken } from "../api/client";
import { AppLayout } from "../components/layout/AppLayout";
import { ClientsPage } from "../pages/ClientsPage";
import { DataExportPage } from "../pages/DataExportPage";
import { FeedbackIssuesPage } from "../pages/FeedbackIssuesPage";
import { LoginPage } from "../pages/LoginPage";
import { OrderDetailsPage } from "../pages/OrderDetailsPage";
import { OrdersPage } from "../pages/OrdersPage";
import { OverviewPage } from "../pages/OverviewPage";
import { SettingsPage } from "../pages/SettingsPage";
import { UsersPage } from "../pages/UsersPage";

function RequireAuth() {
  const location = useLocation();
  return getAccessToken() ? <Outlet /> : <Navigate to="/login" replace state={{ from: location }} />;
}

export function AppRoutes() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route element={<RequireAuth />}>
          <Route element={<AppLayout />}>
            <Route path="/" element={<OverviewPage />} />
            <Route path="/orders" element={<OrdersPage />} />
            <Route path="/orders/:orderId" element={<OrderDetailsPage />} />
            <Route path="/clients" element={<ClientsPage />} />
            <Route path="/data-export" element={<DataExportPage />} />
            <Route path="/feedback" element={<FeedbackIssuesPage />} />
            <Route path="/users" element={<UsersPage />} />
            <Route path="/settings" element={<SettingsPage />} />
          </Route>
        </Route>
      </Routes>
    </BrowserRouter>
  );
}
