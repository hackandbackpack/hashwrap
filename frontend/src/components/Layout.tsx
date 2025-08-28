import React, { ReactNode } from 'react'
import { NavLink } from 'react-router-dom'
import {
  LayoutDashboard,
  Upload,
  Briefcase,
  Search,
  Settings,
  FileText,
  LogOut,
  Moon,
  Sun,
  Monitor,
  User,
  Shield,
  Menu,
  X,
} from 'lucide-react'

import { useAuth } from '@/contexts/AuthContext'
import { useTheme } from '@/contexts/ThemeContext'
import { Button } from '@/components/ui/Button'
import { cn } from '@/lib/utils'

interface LayoutProps {
  children: ReactNode
}

interface NavItem {
  label: string
  to: string
  icon: React.ComponentType<{ className?: string }>
  requiredRoles?: string[]
}

const navigation: NavItem[] = [
  {
    label: 'Dashboard',
    to: '/dashboard',
    icon: LayoutDashboard,
  },
  {
    label: 'Upload',
    to: '/upload',
    icon: Upload,
    requiredRoles: ['admin', 'operator'],
  },
  {
    label: 'Jobs',
    to: '/jobs',
    icon: Briefcase,
  },
  {
    label: 'Results',
    to: '/results',
    icon: Search,
  },
  {
    label: 'Settings',
    to: '/settings',
    icon: Settings,
    requiredRoles: ['admin'],
  },
  {
    label: 'Audit Log',
    to: '/audit',
    icon: FileText,
    requiredRoles: ['admin'],
  },
]

export const Layout: React.FC<LayoutProps> = ({ children }) => {
  const { user, logout, hasRole } = useAuth()
  const { theme, setTheme, actualTheme } = useTheme()
  const [sidebarOpen, setSidebarOpen] = React.useState(false)

  const handleLogout = async () => {
    try {
      await logout()
    } catch (error) {
      console.error('Logout failed:', error)
    }
  }

  const themeIcons = {
    light: Sun,
    dark: Moon,
    system: Monitor,
  }

  const ThemeIcon = themeIcons[theme]

  const cycleTheme = () => {
    const themes = ['light', 'dark', 'system'] as const
    const currentIndex = themes.indexOf(theme)
    const nextIndex = (currentIndex + 1) % themes.length
    setTheme(themes[nextIndex])
  }

  // Filter navigation items based on user role
  const visibleNavItems = navigation.filter(item => {
    if (!item.requiredRoles) return true
    return hasRole(item.requiredRoles)
  })

  return (
    <div className="min-h-screen bg-background">
      {/* Mobile sidebar backdrop */}
      {sidebarOpen && (
        <div 
          className="fixed inset-0 bg-black/50 z-40 lg:hidden"
          onClick={() => setSidebarOpen(false)}
        />
      )}

      {/* Sidebar */}
      <div className={cn(
        'fixed top-0 left-0 z-50 h-full w-64 bg-card border-r border-border transform transition-transform duration-200 ease-in-out lg:translate-x-0',
        sidebarOpen ? 'translate-x-0' : '-translate-x-full'
      )}>
        <div className="flex flex-col h-full">
          {/* Header */}
          <div className="flex items-center justify-between p-4 border-b border-border">
            <div className="flex items-center space-x-2">
              <div className="bg-primary rounded-md p-1.5">
                <Shield className="w-5 h-5 text-primary-foreground" />
              </div>
              <span className="font-semibold text-lg">HashWrap</span>
            </div>
            <Button
              variant="ghost"
              size="icon"
              className="lg:hidden"
              onClick={() => setSidebarOpen(false)}
            >
              <X className="w-4 h-4" />
            </Button>
          </div>

          {/* Navigation */}
          <nav className="flex-1 p-4 space-y-1">
            {visibleNavItems.map((item) => {
              const Icon = item.icon
              return (
                <NavLink
                  key={item.to}
                  to={item.to}
                  className={({ isActive }) =>
                    cn(
                      'flex items-center space-x-3 px-3 py-2 rounded-md text-sm font-medium transition-colors',
                      isActive
                        ? 'bg-primary text-primary-foreground'
                        : 'text-muted-foreground hover:text-foreground hover:bg-accent'
                    )
                  }
                  onClick={() => setSidebarOpen(false)}
                >
                  <Icon className="w-4 h-4" />
                  <span>{item.label}</span>
                </NavLink>
              )
            })}
          </nav>

          {/* User section */}
          <div className="border-t border-border p-4 space-y-2">
            <div className="flex items-center space-x-3 px-3 py-2">
              <div className="bg-secondary rounded-full p-2">
                <User className="w-4 h-4" />
              </div>
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium truncate">{user?.email}</p>
                <p className="text-xs text-muted-foreground capitalize">{user?.role}</p>
              </div>
            </div>

            <div className="flex items-center space-x-2">
              <Button
                variant="ghost"
                size="icon"
                onClick={cycleTheme}
                className="flex-1"
                title={`Current theme: ${theme}`}
              >
                <ThemeIcon className="w-4 h-4" />
              </Button>
              
              <Button
                variant="ghost"
                onClick={handleLogout}
                className="flex-1 justify-start space-x-2"
              >
                <LogOut className="w-4 h-4" />
                <span className="text-sm">Logout</span>
              </Button>
            </div>
          </div>
        </div>
      </div>

      {/* Main content */}
      <div className="lg:pl-64">
        {/* Top bar for mobile */}
        <div className="lg:hidden flex items-center justify-between p-4 border-b border-border bg-card">
          <Button
            variant="ghost"
            size="icon"
            onClick={() => setSidebarOpen(true)}
          >
            <Menu className="w-5 h-5" />
          </Button>
          
          <div className="flex items-center space-x-2">
            <div className="bg-primary rounded-md p-1.5">
              <Shield className="w-4 h-4 text-primary-foreground" />
            </div>
            <span className="font-semibold">HashWrap</span>
          </div>

          <div className="w-10" /> {/* Spacer */}
        </div>

        {/* Page content */}
        <main className="min-h-screen p-4 lg:p-6">
          {children}
        </main>
      </div>
    </div>
  )
}