import { useEffect, useRef, useCallback, useState } from 'react'
import { tokenManager } from '@/lib/api-client'

interface SSEConfig {
  url: string
  onMessage?: (data: unknown) => void
  onError?: (error: Event) => void
  onOpen?: () => void
  onClose?: () => void
  reconnectInterval?: number
  maxReconnectAttempts?: number
  enabled?: boolean
}

interface SSEState {
  connected: boolean
  connecting: boolean
  error: string | null
  reconnectAttempts: number
}

export const useServerSentEvents = ({
  url,
  onMessage,
  onError,
  onOpen,
  onClose,
  reconnectInterval = 5000,
  maxReconnectAttempts = 5,
  enabled = true,
}: SSEConfig) => {
  const [state, setState] = useState<SSEState>({
    connected: false,
    connecting: false,
    error: null,
    reconnectAttempts: 0,
  })

  const eventSourceRef = useRef<EventSource | null>(null)
  const reconnectTimeoutRef = useRef<NodeJS.Timeout | null>(null)
  const shouldReconnectRef = useRef(true)

  const connect = useCallback(() => {
    if (!enabled || eventSourceRef.current?.readyState === EventSource.OPEN) {
      return
    }

    setState(prev => ({ ...prev, connecting: true, error: null }))

    try {
      // Close existing connection if any
      if (eventSourceRef.current) {
        eventSourceRef.current.close()
      }

      // Create new EventSource with auth token
      const token = tokenManager.getToken()
      const eventSourceUrl = token ? `${url}?token=${token}` : url
      
      eventSourceRef.current = new EventSource(eventSourceUrl)

      eventSourceRef.current.onopen = () => {
        setState(prev => ({
          ...prev,
          connected: true,
          connecting: false,
          error: null,
          reconnectAttempts: 0,
        }))
        onOpen?.()
      }

      eventSourceRef.current.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data)
          onMessage?.(data)
        } catch (error) {
          console.error('Failed to parse SSE message:', error)
          onMessage?.(event.data)
        }
      }

      eventSourceRef.current.onerror = (event) => {
        setState(prev => ({
          ...prev,
          connected: false,
          connecting: false,
          error: 'Connection error',
        }))

        onError?.(event)

        // Attempt to reconnect if under max attempts
        if (
          shouldReconnectRef.current &&
          state.reconnectAttempts < maxReconnectAttempts
        ) {
          setState(prev => ({
            ...prev,
            reconnectAttempts: prev.reconnectAttempts + 1,
          }))

          reconnectTimeoutRef.current = setTimeout(() => {
            connect()
          }, reconnectInterval)
        }
      }

      eventSourceRef.current.onclose = () => {
        setState(prev => ({
          ...prev,
          connected: false,
          connecting: false,
        }))
        onClose?.()
      }
    } catch (error) {
      setState(prev => ({
        ...prev,
        connected: false,
        connecting: false,
        error: 'Failed to create connection',
      }))
      console.error('Failed to create EventSource:', error)
    }
  }, [url, enabled, onMessage, onError, onOpen, onClose, reconnectInterval, maxReconnectAttempts, state.reconnectAttempts])

  const disconnect = useCallback(() => {
    shouldReconnectRef.current = false
    
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current)
      reconnectTimeoutRef.current = null
    }

    if (eventSourceRef.current) {
      eventSourceRef.current.close()
      eventSourceRef.current = null
    }

    setState({
      connected: false,
      connecting: false,
      error: null,
      reconnectAttempts: 0,
    })
  }, [])

  const reconnect = useCallback(() => {
    disconnect()
    shouldReconnectRef.current = true
    setState(prev => ({ ...prev, reconnectAttempts: 0 }))
    connect()
  }, [disconnect, connect])

  // Initial connection and cleanup
  useEffect(() => {
    if (enabled) {
      shouldReconnectRef.current = true
      connect()
    } else {
      disconnect()
    }

    return () => {
      disconnect()
    }
  }, [enabled, connect, disconnect])

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      disconnect()
    }
  }, [disconnect])

  return {
    ...state,
    connect,
    disconnect,
    reconnect,
  }
}

// Specialized hook for job updates
export const useJobUpdates = (jobId?: string) => {
  const [lastUpdate, setLastUpdate] = useState<unknown | null>(null)

  const { connected, connecting, error, reconnect } = useServerSentEvents({
    url: `/api/v1/jobs${jobId ? `/${jobId}` : ''}/events/stream`,
    enabled: true,
    onMessage: (data) => {
      setLastUpdate(data)
    },
    onError: (error) => {
      console.error('Job updates SSE error:', error)
    },
  })

  return {
    connected,
    connecting,
    error,
    lastUpdate,
    reconnect,
  }
}

// Specialized hook for system health updates
export const useSystemHealthUpdates = () => {
  const [healthData, setHealthData] = useState<unknown | null>(null)

  const { connected, connecting, error, reconnect } = useServerSentEvents({
    url: '/api/v1/system/health/stream',
    enabled: true,
    onMessage: (data) => {
      setHealthData(data)
    },
    onError: (error) => {
      console.error('System health SSE error:', error)
    },
  })

  return {
    connected,
    connecting,
    error,
    healthData,
    reconnect,
  }
}