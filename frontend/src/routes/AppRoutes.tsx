import { BrowserRouter, Route, Routes } from "react-router-dom";

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

export function AppRoutes() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
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
      </Routes>
    </BrowserRouter>
  );
}
