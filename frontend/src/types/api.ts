// API Response Types
export interface ApiResponse<T = unknown> {
  data?: T
  message?: string
  errors?: Record<string, string[]>
}

export interface PaginatedResponse<T> {
  items: T[]
  total: number
  page: number
  size: number
  pages: number
}

// User Types
export interface User {
  id: string
  email: string
  role: 'admin' | 'operator' | 'viewer'
  is_active: boolean
  last_login: string | null
  created_at: string
  updated_at: string
}

export interface AuthUser extends User {
  permissions: string[]
  totp_enabled: boolean
}

// Authentication Types
export interface LoginRequest {
  email: string
  password: string
  totp_code?: string
}

export interface LoginResponse {
  access_token: string
  token_type: string
  expires_in: number
  user: AuthUser
}

export interface Setup2FAResponse {
  secret: string
  qr_code: string
}

export interface Verify2FARequest {
  totp_code: string
}

// Job Types
export type JobStatus = 
  | 'queued' 
  | 'preparing' 
  | 'running' 
  | 'paused' 
  | 'completed' 
  | 'exhausted' 
  | 'failed' 
  | 'cancelled'

export interface Job {
  id: string
  name: string
  project_id: string
  upload_id: string
  hash_type: string | null
  profile_name: string | null
  status: JobStatus
  total_hashes: number | null
  cracked_count: number
  started_at: string | null
  completed_at: string | null
  created_at: string
  created_by: string
  progress_percentage: number
  runtime_seconds: number | null
}

export interface JobEvent {
  id: string
  job_id: string
  event_type: string
  message: string
  metadata: Record<string, unknown> | null
  created_at: string
}

export interface CreateJobRequest {
  name: string
  project_id: string
  upload_id: string
  hash_type?: string
  profile_name?: string
}

// Upload Types
export interface Upload {
  id: string
  filename: string
  original_filename: string
  file_size: number
  file_hash: string
  project_id: string
  uploaded_by: string
  upload_path: string
  hash_count: number | null
  detected_hash_types: string[]
  created_at: string
}

export interface CreateUploadRequest {
  project_id: string
  file: File
  hash_type_override?: string
}

// Project Types
export interface Project {
  id: string
  name: string
  description: string | null
  is_active: boolean
  created_by: string
  created_at: string
  updated_at: string
}

export interface CreateProjectRequest {
  name: string
  description?: string
}

// Hash Sample Types
export interface HashSample {
  id: string
  hash_value: string
  hash_type: string
  is_cracked: boolean
  plaintext: string | null
  crack_time: string | null
  job_id: string
  created_at: string
}

// Crack Result Types
export interface CrackResult {
  id: string
  hash_value: string
  plaintext: string
  hash_type: string
  crack_method: string
  crack_time: string
  job_id: string
  created_at: string
}

// System Metrics Types
export interface SystemMetrics {
  id: string
  metric_type: string
  metric_name: string
  value: number
  unit: string
  tags: Record<string, string> | null
  timestamp: string
}

export interface SystemHealth {
  status: 'healthy' | 'degraded' | 'unhealthy'
  services: {
    database: 'up' | 'down'
    queue: 'up' | 'down'
    worker: 'up' | 'down'
    storage: 'up' | 'down'
  }
  metrics: {
    active_jobs: number
    queued_jobs: number
    total_hashes_cracked: number
    avg_crack_time: number
  }
}

// Audit Log Types
export interface AuditLog {
  id: string
  user_id: string
  action: string
  resource_type: string
  resource_id: string | null
  old_values: Record<string, unknown> | null
  new_values: Record<string, unknown> | null
  ip_address: string
  user_agent: string
  created_at: string
}

// Webhook Types
export interface WebhookConfig {
  id: string
  name: string
  url: string
  events: string[]
  is_active: boolean
  secret: string | null
  headers: Record<string, string> | null
  created_by: string
  created_at: string
  updated_at: string
}

export interface CreateWebhookRequest {
  name: string
  url: string
  events: string[]
  secret?: string
  headers?: Record<string, string>
}

// Profile Types
export interface Profile {
  id: string
  name: string
  description: string | null
  attack_modes: string[]
  wordlists: string[]
  rules: string[]
  is_active: boolean
  created_by: string
  created_at: string
  updated_at: string
}

export interface CreateProfileRequest {
  name: string
  description?: string
  attack_modes: string[]
  wordlists: string[]
  rules: string[]
}

// Error Types
export interface ApiError {
  message: string
  type: string
  details?: Record<string, unknown>
}