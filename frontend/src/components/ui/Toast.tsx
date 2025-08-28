import React, { createContext, useContext, useState, useCallback, ReactNode } from 'react'
import * as ToastPrimitive from '@radix-ui/react-toast'
import { X, CheckCircle, AlertCircle, AlertTriangle, Info } from 'lucide-react'
import { cn } from '@/lib/utils'

interface Toast {
  id: string
  title?: string
  description?: string
  type: 'success' | 'error' | 'warning' | 'info'
  duration?: number
}

interface ToastContextType {
  toast: (toast: Omit<Toast, 'id'>) => void
  dismiss: (id: string) => void
}

const ToastContext = createContext<ToastContextType | undefined>(undefined)

interface ToastProviderProps {
  children: ReactNode
}

export const ToastProvider: React.FC<ToastProviderProps> = ({ children }) => {
  const [toasts, setToasts] = useState<Toast[]>([])

  const toast = useCallback((newToast: Omit<Toast, 'id'>) => {
    const id = Math.random().toString(36).substr(2, 9)
    const toastWithId = { ...newToast, id }
    
    setToasts(current => [...current, toastWithId])
    
    // Auto-dismiss after duration
    if (newToast.duration !== 0) {
      setTimeout(() => {
        setToasts(current => current.filter(t => t.id !== id))
      }, newToast.duration || 5000)
    }
  }, [])

  const dismiss = useCallback((id: string) => {
    setToasts(current => current.filter(t => t.id !== id))
  }, [])

  const contextValue: ToastContextType = {
    toast,
    dismiss,
  }

  return (
    <ToastContext.Provider value={contextValue}>
      {children}
      <ToastPrimitive.Provider>
        {toasts.map(toast => (
          <ToastComponent key={toast.id} toast={toast} onDismiss={dismiss} />
        ))}
        <ToastPrimitive.Viewport className="fixed top-0 z-[100] flex max-h-screen w-full flex-col-reverse p-4 sm:bottom-0 sm:right-0 sm:top-auto sm:flex-col md:max-w-[420px]" />
      </ToastPrimitive.Provider>
    </ToastContext.Provider>
  )
}

interface ToastComponentProps {
  toast: Toast
  onDismiss: (id: string) => void
}

const ToastComponent: React.FC<ToastComponentProps> = ({ toast, onDismiss }) => {
  const icons = {
    success: CheckCircle,
    error: AlertCircle,
    warning: AlertTriangle,
    info: Info,
  }

  const Icon = icons[toast.type]

  return (
    <ToastPrimitive.Root
      className={cn(
        'group pointer-events-auto relative flex w-full items-center justify-between space-x-4 overflow-hidden rounded-md border p-6 pr-8 shadow-lg transition-all data-[swipe=cancel]:translate-x-0 data-[swipe=end]:translate-x-[var(--radix-toast-swipe-end-x)] data-[swipe=move]:translate-x-[var(--radix-toast-swipe-move-x)] data-[swipe=move]:transition-none data-[state=open]:animate-in data-[state=closed]:animate-out data-[swipe=end]:animate-out data-[state=closed]:fade-out-80 data-[state=closed]:slide-out-to-right-full data-[state=open]:slide-in-from-top-full data-[state=open]:sm:slide-in-from-bottom-full',
        toast.type === 'success' && 'border-success bg-success text-success-foreground',
        toast.type === 'error' && 'border-destructive bg-destructive text-destructive-foreground',
        toast.type === 'warning' && 'border-warning bg-warning text-warning-foreground',
        toast.type === 'info' && 'border-info bg-info text-info-foreground'
      )}
    >
      <div className="flex items-start space-x-3">
        <Icon className="h-5 w-5 shrink-0" />
        <div className="grid gap-1">
          {toast.title && (
            <ToastPrimitive.Title className="text-sm font-semibold">
              {toast.title}
            </ToastPrimitive.Title>
          )}
          {toast.description && (
            <ToastPrimitive.Description className="text-sm opacity-90">
              {toast.description}
            </ToastPrimitive.Description>
          )}
        </div>
      </div>
      <ToastPrimitive.Close
        className="absolute right-2 top-2 rounded-md p-1 text-foreground/50 opacity-0 transition-opacity hover:text-foreground focus:opacity-100 focus:outline-none focus:ring-2 group-hover:opacity-100"
        onClick={() => onDismiss(toast.id)}
      >
        <X className="h-4 w-4" />
      </ToastPrimitive.Close>
    </ToastPrimitive.Root>
  )
}

export const useToast = (): ToastContextType => {
  const context = useContext(ToastContext)
  if (context === undefined) {
    throw new Error('useToast must be used within a ToastProvider')
  }
  return context
}

export const Toaster: React.FC = () => {
  return <ToastProvider>{null}</ToastProvider>
}