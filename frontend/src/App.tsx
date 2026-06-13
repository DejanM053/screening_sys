import { Route, Routes } from "react-router-dom";
import { Sidebar } from "./components/Sidebar";
import { CaseDetail } from "./pages/CaseDetail";
import { MobileApproval } from "./pages/MobileApproval";
import { NetworkExplorer } from "./pages/NetworkExplorer";
import { QueueDashboard } from "./pages/QueueDashboard";

export default function App() {
  return (
    <div className="flex h-screen bg-bg text-text-primary">
      <Sidebar />
      <div className="flex flex-1 flex-col overflow-hidden">
        <Routes>
          <Route path="/" element={<QueueDashboard />} />
          <Route path="/case/:paymentId" element={<CaseDetail />} />
          <Route path="/network/:paymentId" element={<NetworkExplorer />} />
          <Route path="/mobile" element={<MobileApproval />} />
        </Routes>
      </div>
    </div>
  );
}
