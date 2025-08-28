import React, { useState } from 'react'
import { Navigate, useLocation } from 'react-router-dom'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { Eye, EyeOff, Shield, Lock } from 'lucide-react'
import QRCode from 'qrcode'

import { useAuth } from '@/contexts/AuthContext'
import { useTheme } from '@/contexts/ThemeContext'
import { authApi } from '@/lib/api-client'
import { Button } from '@/components/ui/Button'
import { Input } from '@/components/ui/Input'
import { Label } from '@/components/ui/Label'
import { LoadingSpinner } from '@/components/ui/LoadingSpinner'
import { LegalBanner } from '@/components/LegalBanner'
import { cn } from '@/lib/utils'

const loginSchema = z.object({
  email: z.string().email('Please enter a valid email address'),
  password: z.string().min(1, 'Password is required'),
  totp_code: z.string().optional(),
})

type LoginForm = z.infer<typeof loginSchema>

const setup2FASchema = z.object({
  totp_code: z.string().length(6, 'TOTP code must be 6 digits').regex(/^\d+$/, 'TOTP code must contain only numbers'),
})

type Setup2FAForm = z.infer<typeof setup2FASchema>

export const LoginPage: React.FC = () => {
  const { isAuthenticated, login, clearError, error } = useAuth()
  const { actualTheme } = useTheme()
  const location = useLocation()

  const [showPassword, setShowPassword] = useState(false)
  const [isLoading, setIsLoading] = useState(false)
  const [needs2FA, setNeeds2FA] = useState(false)
  const [setup2FA, setSetup2FA] = useState<{ secret: string; qr_code: string } | null>(null)
  const [qrCodeDataUrl, setQrCodeDataUrl] = useState<string>('')

  const from = (location.state as any)?.from?.pathname || '/dashboard'

  const loginForm = useForm<LoginForm>({
    resolver: zodResolver(loginSchema),
    defaultValues: {
      email: '',
      password: '',
      totp_code: '',
    },
  })

  const setup2FAForm = useForm<Setup2FAForm>({
    resolver: zodResolver(setup2FASchema),
    defaultValues: {
      totp_code: '',
    },
  })

  // Redirect if already authenticated
  if (isAuthenticated) {
    return <Navigate to={from} replace />
  }

  const handleLogin = async (data: LoginForm) => {
    setIsLoading(true)
    clearError()

    try {
      await login(data)
    } catch (err: any) {
      if (err.message?.includes('2FA required') || err.message?.includes('TOTP')) {
        setNeeds2FA(true)
        
        // Check if user needs to set up 2FA
        if (err.message?.includes('setup')) {
          try {
            const setup2FAResult = await authApi.setup2FA()
            setSetup2FA(setup2FAResult)
            
            // Generate QR code data URL
            const qrDataUrl = await QRCode.toDataURL(setup2FAResult.qr_code, {
              width: 256,
              margin: 2,
              color: {
                dark: actualTheme === 'dark' ? '#ffffff' : '#000000',
                light: actualTheme === 'dark' ? '#000000' : '#ffffff',
              },
            })
            setQrCodeDataUrl(qrDataUrl)
          } catch (setupError) {
            console.error('Failed to setup 2FA:', setupError)
          }
        }
      }
    } finally {
      setIsLoading(false)
    }
  }

  const handleVerify2FA = async (data: Setup2FAForm) => {
    setIsLoading(true)
    clearError()

    try {
      if (setup2FA) {
        // Verifying setup
        await authApi.verify2FA({ totp_code: data.totp_code })
        setSetup2FA(null)
        setNeeds2FA(false)
        
        // Now login with 2FA
        const loginData = loginForm.getValues()
        await login({ ...loginData, totp_code: data.totp_code })
      } else {
        // Regular 2FA login
        const loginData = loginForm.getValues()
        await login({ ...loginData, totp_code: data.totp_code })
      }
    } catch (err) {
      // Error will be handled by auth context
    } finally {
      setIsLoading(false)
    }
  }

  return (
    <div className="min-h-screen flex flex-col bg-background">
      <LegalBanner />
      
      <div className="flex-1 flex items-center justify-center px-4 py-12">
        <div className="w-full max-w-md space-y-8">
          {/* Header */}
          <div className="text-center">
            <div className="flex items-center justify-center mb-6">
              <div className="bg-primary rounded-full p-3">
                <Shield className="w-8 h-8 text-primary-foreground" />
              </div>
            </div>
            <h1 className="text-3xl font-bold tracking-tight">HashWrap</h1>
            <p className="mt-2 text-muted-foreground">
              {setup2FA ? 'Set up Two-Factor Authentication' : 
               needs2FA ? 'Enter your 2FA code' : 
               'Sign in to your account'}
            </p>
          </div>

          {/* Error Display */}
          {error && (
            <div className="bg-destructive/10 border border-destructive rounded-md p-4">
              <p className="text-destructive text-sm">{error}</p>
            </div>
          )}

          {/* 2FA Setup */}
          {setup2FA && (
            <div className="space-y-6">
              <div className="text-center space-y-4">
                <p className="text-sm text-muted-foreground">
                  Scan this QR code with your authenticator app (Google Authenticator, Authy, etc.)
                </p>
                
                {qrCodeDataUrl && (
                  <div className="flex justify-center">
                    <img
                      src={qrCodeDataUrl}
                      alt="2FA QR Code"
                      className="border rounded-lg"
                    />
                  </div>
                )}

                <div className="bg-muted rounded-md p-3">
                  <p className="text-xs text-muted-foreground mb-1">Manual entry key:</p>
                  <code className="text-sm font-mono break-all">{setup2FA.secret}</code>
                </div>
              </div>

              <form onSubmit={setup2FAForm.handleSubmit(handleVerify2FA)} className="space-y-4">
                <div>
                  <Label htmlFor="setup-totp" required>
                    Verification Code
                  </Label>
                  <Input
                    id="setup-totp"
                    type="text"
                    placeholder="Enter 6-digit code"
                    maxLength={6}
                    {...setup2FAForm.register('totp_code')}
                    error={setup2FAForm.formState.errors.totp_code?.message}
                    className="text-center text-lg tracking-widest font-mono"
                  />
                </div>

                <Button
                  type="submit"
                  className="w-full"
                  loading={isLoading}
                >
                  Verify & Continue
                </Button>
              </form>
            </div>
          )}

          {/* 2FA Verification (existing user) */}
          {needs2FA && !setup2FA && (
            <form onSubmit={setup2FAForm.handleSubmit(handleVerify2FA)} className="space-y-4">
              <div className="text-center mb-4">
                <Lock className="w-8 h-8 mx-auto text-muted-foreground mb-2" />
                <p className="text-sm text-muted-foreground">
                  Enter the 6-digit code from your authenticator app
                </p>
              </div>

              <div>
                <Label htmlFor="totp" required>
                  Authentication Code
                </Label>
                <Input
                  id="totp"
                  type="text"
                  placeholder="000000"
                  maxLength={6}
                  {...setup2FAForm.register('totp_code')}
                  error={setup2FAForm.formState.errors.totp_code?.message}
                  className="text-center text-lg tracking-widest font-mono"
                />
              </div>

              <Button
                type="submit"
                className="w-full"
                loading={isLoading}
              >
                Verify Code
              </Button>

              <Button
                type="button"
                variant="ghost"
                className="w-full"
                onClick={() => {
                  setNeeds2FA(false)
                  loginForm.reset()
                }}
              >
                Back to Login
              </Button>
            </form>
          )}

          {/* Login Form */}
          {!needs2FA && !setup2FA && (
            <form onSubmit={loginForm.handleSubmit(handleLogin)} className="space-y-6">
              <div className="space-y-4">
                <div>
                  <Label htmlFor="email" required>
                    Email Address
                  </Label>
                  <Input
                    id="email"
                    type="email"
                    autoComplete="email"
                    placeholder="Enter your email"
                    {...loginForm.register('email')}
                    error={loginForm.formState.errors.email?.message}
                  />
                </div>

                <div>
                  <Label htmlFor="password" required>
                    Password
                  </Label>
                  <div className="relative">
                    <Input
                      id="password"
                      type={showPassword ? 'text' : 'password'}
                      autoComplete="current-password"
                      placeholder="Enter your password"
                      {...loginForm.register('password')}
                      error={loginForm.formState.errors.password?.message}
                      className="pr-10"
                    />
                    <button
                      type="button"
                      className="absolute right-3 top-3 text-muted-foreground hover:text-foreground"
                      onClick={() => setShowPassword(!showPassword)}
                    >
                      {showPassword ? (
                        <EyeOff className="w-4 h-4" />
                      ) : (
                        <Eye className="w-4 h-4" />
                      )}
                    </button>
                  </div>
                </div>
              </div>

              <Button
                type="submit"
                className="w-full"
                loading={isLoading}
              >
                Sign In
              </Button>
            </form>
          )}

          {/* Footer */}
          <div className="text-center text-xs text-muted-foreground">
            <p>
              By signing in, you agree to comply with all applicable laws and regulations
              regarding password cracking and security testing.
            </p>
          </div>
        </div>
      </div>
    </div>
  )
}