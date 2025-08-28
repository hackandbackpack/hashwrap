import { useContext } from 'react'
import { useToast as useToastBase } from '@/components/ui/Toast'

// Re-export the base hook with additional convenience methods
export const useToast = () => {
  const { toast, dismiss } = useToastBase()

  return {
    toast,
    dismiss,
    success: (title: string, description?: string) => 
      toast({ type: 'success', title, description }),
    error: (title: string, description?: string) => 
      toast({ type: 'error', title, description }),
    warning: (title: string, description?: string) => 
      toast({ type: 'warning', title, description }),
    info: (title: string, description?: string) => 
      toast({ type: 'info', title, description }),
  }
}