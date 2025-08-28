import React, { useState, useEffect } from 'react'
import { AlertTriangle, X } from 'lucide-react'
import { Button } from '@/components/ui/Button'
import { cn } from '@/lib/utils'

const LEGAL_BANNER_KEY = 'hashwrap-legal-accepted'

export const LegalBanner: React.FC = () => {
  const [isVisible, setIsVisible] = useState(false)
  const [isExpanded, setIsExpanded] = useState(false)

  useEffect(() => {
    const accepted = localStorage.getItem(LEGAL_BANNER_KEY)
    if (!accepted) {
      setIsVisible(true)
    }
  }, [])

  const handleAccept = () => {
    localStorage.setItem(LEGAL_BANNER_KEY, 'true')
    setIsVisible(false)
  }

  const handleDismiss = () => {
    setIsVisible(false)
  }

  if (!isVisible) {
    return null
  }

  return (
    <div className="bg-warning text-warning-foreground border-b border-warning/20">
      <div className="container mx-auto px-4 py-3">
        <div className="flex items-start gap-3">
          <AlertTriangle className="w-5 h-5 shrink-0 mt-0.5" />
          
          <div className="flex-1 min-w-0">
            <div className="flex items-center justify-between mb-2">
              <h3 className="font-semibold text-sm">
                AUTHORIZED USE ONLY - LEGAL NOTICE
              </h3>
              <button
                onClick={handleDismiss}
                className="text-warning-foreground/70 hover:text-warning-foreground"
              >
                <X className="w-4 h-4" />
              </button>
            </div>
            
            <div className="text-sm space-y-2">
              <p>
                This system is restricted to authorized users only. By accessing this system, you acknowledge that:
              </p>
              
              <div className={cn(
                'overflow-hidden transition-all duration-200',
                isExpanded ? 'max-h-96' : 'max-h-0'
              )}>
                <ul className="list-disc list-inside space-y-1 mt-2 text-xs">
                  <li>You have explicit authorization to perform password cracking activities</li>
                  <li>You will only test hashes that you own or have written permission to test</li>
                  <li>You understand that unauthorized access to computer systems is illegal</li>
                  <li>All activities are logged and monitored for compliance and security purposes</li>
                  <li>You agree to comply with all applicable local, state, and federal laws</li>
                  <li>Any misuse of this system may result in criminal and/or civil penalties</li>
                  <li>You assume full responsibility for your actions on this system</li>
                </ul>
                
                <div className="mt-3 p-2 bg-warning-foreground/10 rounded text-xs">
                  <p className="font-medium mb-1">Ethical Use Guidelines:</p>
                  <ul className="list-disc list-inside space-y-0.5">
                    <li>Use only for legitimate security testing and research</li>
                    <li>Obtain proper authorization before testing any systems</li>
                    <li>Protect and secure any cracked passwords appropriately</li>
                    <li>Report vulnerabilities through proper channels</li>
                  </ul>
                </div>
              </div>
              
              <div className="flex items-center gap-3 mt-3">
                <Button
                  onClick={() => setIsExpanded(!isExpanded)}
                  variant="outline"
                  size="sm"
                  className="text-xs bg-warning-foreground/10 border-warning-foreground/20 hover:bg-warning-foreground/20"
                >
                  {isExpanded ? 'Show Less' : 'Read Full Terms'}
                </Button>
                
                <Button
                  onClick={handleAccept}
                  size="sm"
                  className="text-xs bg-warning-foreground text-warning hover:bg-warning-foreground/90"
                >
                  I Understand & Accept
                </Button>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}