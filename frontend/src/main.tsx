import React from "react";
import ReactDOM from "react-dom/client";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter, Routes, Route } from "react-router-dom";

const queryClient = new QueryClient();

function HomePage() {
  return (
    <div className="min-h-screen bg-purple-50/40 flex flex-col justify-between">
      <header className="bg-white border-b border-purple-100 px-6 py-4 flex items-center justify-between">
        <div>
          <span className="text-2xl font-bold text-purple-700 tracking-tight">PawCare</span>
          <span className="ml-3 text-sm text-amber-700 font-medium">Book • Care • Stay Connected</span>
        </div>
      </header>
      <main className="max-w-4xl mx-auto px-6 py-16 text-center">
        <h1 className="text-4xl font-bold text-slate-900 mb-4">
          Trusted Care for Your Pet When You Cannot Be There
        </h1>
        <p className="text-lg text-slate-600 mb-8">
          Verified caregivers, structured daily Care Plans, and real-time photo updates.
        </p>
      </main>
    </div>
  );
}

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<HomePage />} />
        </Routes>
      </BrowserRouter>
    </QueryClientProvider>
  </React.StrictMode>
);
