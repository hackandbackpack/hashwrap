import React from 'react'
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { AuthProvider } from '@/contexts/AuthContext'
import { ThemeProvider } from '@/contexts/ThemeContext'
import { ProtectedRoute, AdminRoute, OperatorRoute } from '@/components/ProtectedRoute'
import { Layout } from '@/components/Layout'
import { Toaster } from '@/components/ui/Toast'

// Pages
import { LoginPage } from '@/pages/LoginPage'
import { DashboardPage } from '@/pages/DashboardPage'
import { UploadPage } from '@/pages/UploadPage'
import { JobsPage } from '@/pages/JobsPage'
import { JobDetailPage } from '@/pages/JobDetailPage'
import { ResultsPage } from '@/pages/ResultsPage'
import { SettingsPage } from '@/pages/SettingsPage'
import { AuditLogPage } from '@/pages/AuditLogPage'
import { UnauthorizedPage } from '@/pages/UnauthorizedPage'
import { NotFoundPage } from '@/pages/NotFoundPage'

// Create query client
const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: (failureCount, error) => {
        // Don't retry on 401/403 errors
        if (error && typeof error === 'object' && 'response' in error) {
          const status = (error as any).response?.status
          if (status === 401 || status === 403) return false
        }
        return failureCount < 2
      },
      refetchOnWindowFocus: false,
    },
  },
})

export const App: React.FC = () => {
  return (
    <QueryClientProvider client={queryClient}>
      <ThemeProvider>
        <AuthProvider>
          <Router>
            <div className="min-h-screen bg-background font-sans antialiased">
              <Routes>
                {/* Public routes */}
                <Route path="/login" element={<LoginPage />} />
                <Route path="/unauthorized" element={<UnauthorizedPage />} />

                {/* Protected routes with layout */}
                <Route
                  path="/*"
                  element={
                    <ProtectedRoute>
                      <Layout>
                        <Routes>
                          {/* Redirect root to dashboard */}
                          <Route path="/" element={<Navigate to="/dashboard" replace />} />
                          
                          {/* Dashboard - accessible by all authenticated users */}
                          <Route path="/dashboard" element={<DashboardPage />} />
                          
                          {/* Upload - accessible by admin/operator */}
                          <Route 
                            path="/upload" 
                            element={
                              <OperatorRoute>
                                <UploadPage />
                              </OperatorRoute>
                            } 
                          />
                          
                          {/* Jobs - accessible by all authenticated users */}
                          <Route path="/jobs" element={<JobsPage />} />
                          <Route path="/jobs/:id" element={<JobDetailPage />} />
                          
                          {/* Results - accessible by all authenticated users */}
                          <Route path="/results" element={<ResultsPage />} />
                          
                          {/* Settings - admin only */}
                          <Route 
                            path="/settings" 
                            element={
                              <AdminRoute>
                                <SettingsPage />
                              </AdminRoute>
                            } 
                          />
                          
                          {/* Audit logs - admin only */}
                          <Route 
                            path="/audit" 
                            element={
                              <AdminRoute>
                                <AuditLogPage />
                              </AdminRoute>
                            } 
                          />
                          
                          {/* 404 for unknown routes */}
                          <Route path="*" element={<NotFoundPage />} />
                        </Routes>
                      </Layout>
                    </ProtectedRoute>
                  }
                />
              </Routes>
              
              {/* Toast notifications */}
              <Toaster />
            </div>
          </Router>
        </AuthProvider>
      </ThemeProvider>
    </QueryClientProvider>
  )
}