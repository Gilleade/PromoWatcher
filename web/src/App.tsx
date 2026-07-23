import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
import { Navbar } from './components/Navbar'
import { FeedPage } from './pages/FeedPage'
import { ProductProfilePage } from './pages/ProductProfilePage'
import { FavoritesPage } from './pages/FavoritesPage'
import { CouponsPage } from './pages/CouponsPage'
import { AlertsAdminPage } from './pages/AlertsAdminPage'
import { ProductsAdminPage } from './pages/ProductsAdminPage'

const queryClient = new QueryClient({
  defaultOptions: { queries: { staleTime: 30_000, retry: 1 } },
})

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <Navbar />
        <main className="app-main">
          <Routes>
            <Route path="/" element={<FeedPage />} />
            <Route path="/produtos/:id" element={<ProductProfilePage />} />
            <Route path="/favoritos" element={<FavoritesPage />} />
            <Route path="/cupons" element={<CouponsPage />} />
            <Route path="/alertas" element={<AlertsAdminPage />} />
            <Route path="/admin" element={<ProductsAdminPage />} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </main>
      </BrowserRouter>
    </QueryClientProvider>
  )
}
