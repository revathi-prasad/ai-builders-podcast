/**
 * API Client for Podcast Generator Backend
 */

const API_BASE = '/api'

// Types
export interface ContentInput {
  type: string
  source: string
}

export interface GenerateRequest {
  user_request: string
  contents: ContentInput[]
  target_language: string
  target_duration_minutes: number
  episode_format: string
  audience_level: string
}

export interface GenerateResponse {
  job_id: string
  status: string
  message: string
}

export interface ScriptSegment {
  speaker: string
  text: string
  timestamp?: number
  fact_ids?: string[]
}

export interface VerificationResult {
  checker: string
  passed: boolean
  score: number
  issues: string[]
  suggestions: string[]
}

export interface JobResult {
  final_script?: string
  audio_file_path?: string
  quality_score?: number
  fm_reward?: number
  duration_minutes?: number
  segments?: ScriptSegment[]
  verification_results?: VerificationResult[]
  metadata?: {
    trace_id?: string
    language?: string
    format?: string
    handoff_count?: number
  }
}

export interface JobStatus {
  job_id: string
  status: 'pending' | 'processing' | 'completed' | 'failed'
  progress: number
  current_step: string
  created_at: string
  completed_at?: string
  result?: JobResult
  error?: string
}

export interface JobsResponse {
  jobs: JobStatus[]
  total: number
}

export interface FeedbackRequest {
  job_id: string
  rating: number
  feedback_type: 'explicit' | 'pairwise' | 'implicit'
  comments?: string
  listen_percentage?: number
  would_share?: boolean
  aspects?: {
    content_quality?: number
    audio_quality?: number
    engagement?: number
    accuracy?: number
  }
}

export interface PairwiseFeedbackRequest {
  winner_job_id: string
  loser_job_id: string
  feedback_type: 'pairwise'
  comments?: string
}

export interface FeedbackStats {
  total_feedback: number
  avg_rating: number
  feedback_by_type: Record<string, number>
  rating_distribution: Record<string, number>
}

// API Functions
async function fetchApi<T>(
  endpoint: string,
  options: RequestInit = {}
): Promise<T> {
  const response = await fetch(`${API_BASE}${endpoint}`, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...options.headers,
    },
  })

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Unknown error' }))
    throw new Error(error.detail || `HTTP ${response.status}`)
  }

  return response.json()
}

// Health Check
export async function healthCheck() {
  return fetchApi<{ status: string; components: Record<string, string> }>('/health')
}

// Generate Podcast
export async function generatePodcast(request: GenerateRequest): Promise<GenerateResponse> {
  return fetchApi<GenerateResponse>('/generate', {
    method: 'POST',
    body: JSON.stringify(request),
  })
}

// Get Job Status
export async function getJobStatus(jobId: string): Promise<JobStatus> {
  return fetchApi<JobStatus>(`/jobs/${jobId}`)
}

// List Jobs
export async function getJobs(limit: number = 10): Promise<JobsResponse> {
  return fetchApi<JobsResponse>(`/jobs?limit=${limit}`)
}

// Submit Feedback
export async function submitFeedback(feedback: FeedbackRequest): Promise<{ success: boolean; message: string }> {
  return fetchApi<{ success: boolean; message: string }>('/feedback', {
    method: 'POST',
    body: JSON.stringify(feedback),
  })
}

// Submit Pairwise Feedback
export async function submitPairwiseFeedback(feedback: PairwiseFeedbackRequest): Promise<{ success: boolean; message: string }> {
  return fetchApi<{ success: boolean; message: string }>('/feedback/pairwise', {
    method: 'POST',
    body: JSON.stringify(feedback),
  })
}

// Get Feedback Stats
export async function getFeedbackStats(): Promise<FeedbackStats> {
  return fetchApi<FeedbackStats>('/feedback/stats')
}

// Get Script
export async function getScript(jobId: string): Promise<{
  job_id: string
  script: string
  segments: ScriptSegment[]
  quality_score: number
  fm_reward: number
  verification_results: VerificationResult[]
}> {
  return fetchApi(`/script/${jobId}`)
}

// Upload File
export async function uploadFile(file: File): Promise<{ file_id: string; path: string }> {
  const formData = new FormData()
  formData.append('file', file)

  const response = await fetch(`${API_BASE}/upload`, {
    method: 'POST',
    body: formData,
  })

  if (!response.ok) {
    throw new Error('Upload failed')
  }

  return response.json()
}

// WebSocket for real-time updates
export function createJobWebSocket(jobId: string): WebSocket {
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
  const host = window.location.host
  return new WebSocket(`${protocol}//${host}/ws/jobs/${jobId}`)
}
