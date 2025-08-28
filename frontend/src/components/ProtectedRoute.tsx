import React from 'react'
import { Navigate, useLocation } from 'react-router-dom'
import { useAuth } from '@/contexts/AuthContext'
import { LoadingSpinner } from '@/components/ui/LoadingSpinner'

interface ProtectedRouteProps {
  children: React.ReactNode
  requiredRoles?: string | string[]
  requiredPermissions?: string | string[]
  redirectTo?: string
}

export const ProtectedRoute: React.FC<ProtectedRouteProps> = ({
  children,
  requiredRoles = [],
  requiredPermissions = [],
  redirectTo = '/login',
}) => {
  const { isAuthenticated, isLoading, user, hasRole, checkPermission } = useAuth()
  const location = useLocation()

  if (isLoading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <LoadingSpinner size="lg" />
      </div>
    )
  }

  if (!isAuthenticated || !user) {
    return <Navigate to={redirectTo} state={{ from: location }} replace />
  }

  // Check role requirements
  const roleArray = Array.isArray(requiredRoles) ? requiredRoles : [requiredRoles]
  if (roleArray.length > 0 && !hasRole(roleArray)) {
    return <Navigate to="/unauthorized" replace />
  }

  // Check permission requirements
  const permissionArray = Array.isArray(requiredPermissions) ? requiredPermissions : [requiredPermissions]
  if (permissionArray.length > 0) {
    const hasRequiredPermissions = permissionArray.every(permission => 
      checkPermission(permission)
    )
    
    if (!hasRequiredPermissions) {
      return <Navigate to="/unauthorized" replace />
    }
  }

  return <>{children}</>
}

interface AdminRouteProps {
  children: React.ReactNode
}

export const AdminRoute: React.FC<AdminRouteProps> = ({ children }) => {
  return (
    <ProtectedRoute requiredRoles="admin">
      {children}
    </ProtectedRoute>
  )
}

interface OperatorRouteProps {
  children: React.ReactNode
}

export const OperatorRoute: React.FC<OperatorRouteProps> = ({ children }) => {
  return (
    <ProtectedRoute requiredRoles={['admin', 'operator']}>
      {children}
    </ProtectedRoute>
  )
}