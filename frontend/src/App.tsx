import { Routes, Route } from "react-router-dom";
import { Layout } from "./components/Layout";
import { NewRun } from "./pages/NewRun";
import { Review } from "./pages/Review";

export function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route path="/" element={<NewRun />} />
        <Route path="/runs/:id" element={<Review />} />
      </Route>
    </Routes>
  );
}