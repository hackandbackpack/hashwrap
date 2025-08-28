import axios, { AxiosError, AxiosResponse } from 'axios'
import type {
  ApiResponse,
  PaginatedResponse,
  LoginRequest,
  LoginResponse,
  AuthUser,
  Setup2FAResponse,
  Verify2FARequest,
  Job,
  JobEvent,
  CreateJobRequest,
  Upload,
  CreateUploadRequest,
  Project,
  CreateProjectRequest,
  HashSample,
  CrackResult,
  SystemHealth,
  SystemMetrics,
  AuditLog,
  WebhookConfig,
  CreateWebhookRequest,
  Profile,
  CreateProfileRequest,
  User,
  ApiError,
} from '@/types/api'

// Create axios instance with base configuration
const apiClient = axios.create({
  baseURL: '/api/v1',
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json',
  },
})

// Token management
const TOKEN_KEY = 'hashwrap_token'

export const tokenManager = {
  getToken: (): string | null => {
    return localStorage.getItem(TOKEN_KEY)
  },
  setToken: (token: string): void => {
    localStorage.setItem(TOKEN_KEY, token)
  },
  clearToken: (): void => {
    localStorage.removeItem(TOKEN_KEY)
  },
}

// Request interceptor to add auth token
apiClient.interceptors.request.use(
  (config) => {
    const token = tokenManager.getToken()
    if (token) {
      config.headers.Authorization = `Bearer ${token}`
    }
    return config
  },
  (error) => Promise.reject(error)
)

// Response interceptor for error handling
apiClient.interceptors.response.use(
  (response: AxiosResponse) => response,
  (error: AxiosError) => {
    if (error.response?.status === 401) {
      tokenManager.clearToken()
      window.location.href = '/login'
    }
    return Promise.reject(error)
  }
)

// Helper function to handle API responses
const handleApiResponse = <T>(response: AxiosResponse<ApiResponse<T>>): T => {
  if (response.data.data !== undefined) {
    return response.data.data
  }
  throw new Error(response.data.message || 'Unknown error')
}

// Helper function to handle API errors
const handleApiError = (error: AxiosError<ApiResponse>): never => {
  const apiError: ApiError = {
    message: 'An unexpected error occurred',
    type: 'unknown_error',
  }

  if (error.response?.data) {
    apiError.message = error.response.data.message || apiError.message
    apiError.details = error.response.data.errors
  } else if (error.message) {
    apiError.message = error.message
  }

  throw apiError
}

// Authentication API
export const authApi = {
  login: async (credentials: LoginRequest): Promise<LoginResponse> => {
    try {
      const response = await apiClient.post<ApiResponse<LoginResponse>>('/auth/login', credentials)
      const data = handleApiResponse(response)
      tokenManager.setToken(data.access_token)
      return data
    } catch (error) {
      handleApiError(error as AxiosError<ApiResponse>)
    }
  },

  logout: async (): Promise<void> => {
    try {
      await apiClient.post('/auth/logout')
    } catch (error) {
      // Continue with logout even if API call fails
      console.warn('Logout API call failed:', error)
    } finally {
      tokenManager.clearToken()
    }
  },

  getCurrentUser: async (): Promise<AuthUser> => {
    try {
      const response = await apiClient.get<ApiResponse<AuthUser>>('/auth/me')
      return handleApiResponse(response)
    } catch (error) {
      handleApiError(error as AxiosError<ApiResponse>)
    }
  },

  setup2FA: async (): Promise<Setup2FAResponse> => {
    try {
      const response = await apiClient.post<ApiResponse<Setup2FAResponse>>('/auth/2fa/setup')
      return handleApiResponse(response)
    } catch (error) {
      handleApiError(error as AxiosError<ApiResponse>)
    }
  },

  verify2FA: async (data: Verify2FARequest): Promise<void> => {
    try {
      await apiClient.post<ApiResponse<void>>('/auth/2fa/verify', data)
    } catch (error) {
      handleApiError(error as AxiosError<ApiResponse>)
    }
  },

  disable2FA: async (data: Verify2FARequest): Promise<void> => {
    try {
      await apiClient.post<ApiResponse<void>>('/auth/2fa/disable', data)
    } catch (error) {
      handleApiError(error as AxiosError<ApiResponse>)
    }
  },
}

// Projects API
export const projectsApi = {
  getProjects: async (): Promise<Project[]> => {
    try {
      const response = await apiClient.get<ApiResponse<Project[]>>('/projects')
      return handleApiResponse(response)
    } catch (error) {
      handleApiError(error as AxiosError<ApiResponse>)
    }
  },

  getProject: async (id: string): Promise<Project> => {
    try {
      const response = await apiClient.get<ApiResponse<Project>>(`/projects/${id}`)
      return handleApiResponse(response)
    } catch (error) {
      handleApiError(error as AxiosError<ApiResponse>)
    }
  },

  createProject: async (data: CreateProjectRequest): Promise<Project> => {
    try {
      const response = await apiClient.post<ApiResponse<Project>>('/projects', data)
      return handleApiResponse(response)
    } catch (error) {
      handleApiError(error as AxiosError<ApiResponse>)
    }
  },

  updateProject: async (id: string, data: Partial<CreateProjectRequest>): Promise<Project> => {
    try {
      const response = await apiClient.put<ApiResponse<Project>>(`/projects/${id}`, data)
      return handleApiResponse(response)
    } catch (error) {
      handleApiError(error as AxiosError<ApiResponse>)
    }
  },

  deleteProject: async (id: string): Promise<void> => {
    try {
      await apiClient.delete(`/projects/${id}`)
    } catch (error) {
      handleApiError(error as AxiosError<ApiResponse>)
    }
  },
}

// Uploads API
export const uploadsApi = {
  getUploads: async (projectId?: string): Promise<Upload[]> => {
    try {
      const params = projectId ? { project_id: projectId } : {}
      const response = await apiClient.get<ApiResponse<Upload[]>>('/uploads', { params })
      return handleApiResponse(response)
    } catch (error) {
      handleApiError(error as AxiosError<ApiResponse>)
    }
  },

  getUpload: async (id: string): Promise<Upload> => {
    try {
      const response = await apiClient.get<ApiResponse<Upload>>(`/uploads/${id}`)
      return handleApiResponse(response)
    } catch (error) {
      handleApiError(error as AxiosError<ApiResponse>)
    }
  },

  createUpload: async (data: CreateUploadRequest): Promise<Upload> => {
    try {
      const formData = new FormData()
      formData.append('file', data.file)
      formData.append('project_id', data.project_id)
      if (data.hash_type_override) {
        formData.append('hash_type_override', data.hash_type_override)
      }

      const response = await apiClient.post<ApiResponse<Upload>>('/uploads', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      })
      return handleApiResponse(response)
    } catch (error) {
      handleApiError(error as AxiosError<ApiResponse>)
    }
  },

  deleteUpload: async (id: string): Promise<void> => {
    try {
      await apiClient.delete(`/uploads/${id}`)
    } catch (error) {
      handleApiError(error as AxiosError<ApiResponse>)
    }
  },
}

// Jobs API
export const jobsApi = {
  getJobs: async (params?: { 
    status?: JobStatus
    project_id?: string
    page?: number
    size?: number 
  }): Promise<PaginatedResponse<Job>> => {
    try {
      const response = await apiClient.get<ApiResponse<PaginatedResponse<Job>>>('/jobs', { params })
      return handleApiResponse(response)
    } catch (error) {
      handleApiError(error as AxiosError<ApiResponse>)
    }
  },

  getJob: async (id: string): Promise<Job> => {
    try {
      const response = await apiClient.get<ApiResponse<Job>>(`/jobs/${id}`)
      return handleApiResponse(response)
    } catch (error) {
      handleApiError(error as AxiosError<ApiResponse>)
    }
  },

  createJob: async (data: CreateJobRequest): Promise<Job> => {
    try {
      const response = await apiClient.post<ApiResponse<Job>>('/jobs', data)
      return handleApiResponse(response)
    } catch (error) {
      handleApiError(error as AxiosError<ApiResponse>)
    }
  },

  pauseJob: async (id: string): Promise<void> => {
    try {
      await apiClient.post(`/jobs/${id}/pause`)
    } catch (error) {
      handleApiError(error as AxiosError<ApiResponse>)
    }
  },

  resumeJob: async (id: string): Promise<void> => {
    try {
      await apiClient.post(`/jobs/${id}/resume`)
    } catch (error) {
      handleApiError(error as AxiosError<ApiResponse>)
    }
  },

  cancelJob: async (id: string): Promise<void> => {
    try {
      await apiClient.post(`/jobs/${id}/cancel`)
    } catch (error) {
      handleApiError(error as AxiosError<ApiResponse>)
    }
  },

  getJobEvents: async (id: string): Promise<JobEvent[]> => {
    try {
      const response = await apiClient.get<ApiResponse<JobEvent[]>>(`/jobs/${id}/events`)
      return handleApiResponse(response)
    } catch (error) {
      handleApiError(error as AxiosError<ApiResponse>)
    }
  },

  getJobResults: async (id: string): Promise<CrackResult[]> => {
    try {
      const response = await apiClient.get<ApiResponse<CrackResult[]>>(`/jobs/${id}/results`)
      return handleApiResponse(response)
    } catch (error) {
      handleApiError(error as AxiosError<ApiResponse>)
    }
  },
}

// Results API
export const resultsApi = {
  searchResults: async (params: {
    query?: string
    hash_type?: string
    job_id?: string
    page?: number
    size?: number
  }): Promise<PaginatedResponse<CrackResult>> => {
    try {
      const response = await apiClient.get<ApiResponse<PaginatedResponse<CrackResult>>>('/results/search', { params })
      return handleApiResponse(response)
    } catch (error) {
      handleApiError(error as AxiosError<ApiResponse>)
    }
  },

  exportResults: async (params: {
    format: 'csv' | 'json'
    job_id?: string
    hash_type?: string
  }): Promise<Blob> => {
    try {
      const response = await apiClient.get('/results/export', {
        params,
        responseType: 'blob',
      })
      return response.data
    } catch (error) {
      handleApiError(error as AxiosError<ApiResponse>)
    }
  },

  revealPassword: async (resultId: string): Promise<string> => {
    try {
      const response = await apiClient.post<ApiResponse<{ password: string }>>(`/results/${resultId}/reveal`)
      return handleApiResponse(response).password
    } catch (error) {
      handleApiError(error as AxiosError<ApiResponse>)
    }
  },
}

// System API
export const systemApi = {
  getHealth: async (): Promise<SystemHealth> => {
    try {
      const response = await apiClient.get<ApiResponse<SystemHealth>>('/system/health')
      return handleApiResponse(response)
    } catch (error) {
      handleApiError(error as AxiosError<ApiResponse>)
    }
  },

  getMetrics: async (params?: {
    metric_type?: string
    start_time?: string
    end_time?: string
  }): Promise<SystemMetrics[]> => {
    try {
      const response = await apiClient.get<ApiResponse<SystemMetrics[]>>('/system/metrics', { params })
      return handleApiResponse(response)
    } catch (error) {
      handleApiError(error as AxiosError<ApiResponse>)
    }
  },
}

// Users API (Admin only)
export const usersApi = {
  getUsers: async (): Promise<User[]> => {
    try {
      const response = await apiClient.get<ApiResponse<User[]>>('/users')
      return handleApiResponse(response)
    } catch (error) {
      handleApiError(error as AxiosError<ApiResponse>)
    }
  },

  createUser: async (data: {
    email: string
    password: string
    role: 'admin' | 'operator' | 'viewer'
  }): Promise<User> => {
    try {
      const response = await apiClient.post<ApiResponse<User>>('/users', data)
      return handleApiResponse(response)
    } catch (error) {
      handleApiError(error as AxiosError<ApiResponse>)
    }
  },

  updateUser: async (id: string, data: Partial<{
    email: string
    role: 'admin' | 'operator' | 'viewer'
    is_active: boolean
  }>): Promise<User> => {
    try {
      const response = await apiClient.put<ApiResponse<User>>(`/users/${id}`, data)
      return handleApiResponse(response)
    } catch (error) {
      handleApiError(error as AxiosError<ApiResponse>)
    }
  },

  deleteUser: async (id: string): Promise<void> => {
    try {
      await apiClient.delete(`/users/${id}`)
    } catch (error) {
      handleApiError(error as AxiosError<ApiResponse>)
    }
  },
}

// Webhooks API
export const webhooksApi = {
  getWebhooks: async (): Promise<WebhookConfig[]> => {
    try {
      const response = await apiClient.get<ApiResponse<WebhookConfig[]>>('/webhooks')
      return handleApiResponse(response)
    } catch (error) {
      handleApiError(error as AxiosError<ApiResponse>)
    }
  },

  createWebhook: async (data: CreateWebhookRequest): Promise<WebhookConfig> => {
    try {
      const response = await apiClient.post<ApiResponse<WebhookConfig>>('/webhooks', data)
      return handleApiResponse(response)
    } catch (error) {
      handleApiError(error as AxiosError<ApiResponse>)
    }
  },

  updateWebhook: async (id: string, data: Partial<CreateWebhookRequest>): Promise<WebhookConfig> => {
    try {
      const response = await apiClient.put<ApiResponse<WebhookConfig>>(`/webhooks/${id}`, data)
      return handleApiResponse(response)
    } catch (error) {
      handleApiError(error as AxiosError<ApiResponse>)
    }
  },

  deleteWebhook: async (id: string): Promise<void> => {
    try {
      await apiClient.delete(`/webhooks/${id}`)
    } catch (error) {
      handleApiError(error as AxiosError<ApiResponse>)
    }
  },

  testWebhook: async (id: string): Promise<void> => {
    try {
      await apiClient.post(`/webhooks/${id}/test`)
    } catch (error) {
      handleApiError(error as AxiosError<ApiResponse>)
    }
  },
}

// Profiles API
export const profilesApi = {
  getProfiles: async (): Promise<Profile[]> => {
    try {
      const response = await apiClient.get<ApiResponse<Profile[]>>('/profiles')
      return handleApiResponse(response)
    } catch (error) {
      handleApiError(error as AxiosError<ApiResponse>)
    }
  },

  createProfile: async (data: CreateProfileRequest): Promise<Profile> => {
    try {
      const response = await apiClient.post<ApiResponse<Profile>>('/profiles', data)
      return handleApiResponse(response)
    } catch (error) {
      handleApiError(error as AxiosError<ApiResponse>)
    }
  },

  updateProfile: async (id: string, data: Partial<CreateProfileRequest>): Promise<Profile> => {
    try {
      const response = await apiClient.put<ApiResponse<Profile>>(`/profiles/${id}`, data)
      return handleApiResponse(response)
    } catch (error) {
      handleApiError(error as AxiosError<ApiResponse>)
    }
  },

  deleteProfile: async (id: string): Promise<void> => {
    try {
      await apiClient.delete(`/profiles/${id}`)
    } catch (error) {
      handleApiError(error as AxiosError<ApiResponse>)
    }
  },
}

// Audit Logs API
export const auditApi = {
  getAuditLogs: async (params?: {
    user_id?: string
    action?: string
    resource_type?: string
    start_date?: string
    end_date?: string
    page?: number
    size?: number
  }): Promise<PaginatedResponse<AuditLog>> => {
    try {
      const response = await apiClient.get<ApiResponse<PaginatedResponse<AuditLog>>>('/audit', { params })
      return handleApiResponse(response)
    } catch (error) {
      handleApiError(error as AxiosError<ApiResponse>)
    }
  },
}

export default apiClient