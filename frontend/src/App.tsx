import { BrowserRouter, Link, Route, Routes } from "react-router-dom";
import { Layout } from "./components/Layout";
import { OverviewPage } from "./pages/OverviewPage";
import { SignalsPage } from "./pages/SignalsPage";
import { DrugDetailPage } from "./pages/DrugDetailPage";
import { TrialsPage } from "./pages/TrialsPage";
import { ReviewsPage } from "./pages/ReviewsPage";
import { MethodologyPage } from "./pages/MethodologyPage";
import { EmptyState } from "./components/States";

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route element={<Layout />}>
          <Route path="/" element={<OverviewPage />} />
          <Route path="/signals" element={<SignalsPage />} />
          <Route path="/trials" element={<TrialsPage />} />
          <Route path="/reviews" element={<ReviewsPage />} />
          <Route path="/methodology" element={<MethodologyPage />} />
          <Route path="/drug/:name" element={<DrugDetailPage />} />
          <Route
            path="*"
            element={
              <div className="page">
                <EmptyState
                  title="Page not found"
                  message="That route does not exist in the EvidenceRadar dashboard."
                  action={
                    <Link className="btn btn--primary" to="/">
                      Back to Overview
                    </Link>
                  }
                />
              </div>
            }
          />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}
