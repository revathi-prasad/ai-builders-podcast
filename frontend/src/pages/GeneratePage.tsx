import { useState, useEffect, useCallback } from 'react'
import { useMutation } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { Upload, Link as LinkIcon, FileText, Loader2, CheckCircle2, AlertCircle, Play, ArrowRight } from 'lucide-react'
import { generatePodcast, getJobStatus, createJobWebSocket, submitFeedback, type GenerateRequest, type JobStatus } from '../api/client'
import { PodcastPlayer, FeedbackModal } from '../components'
import type { FeedbackData } from '../components'

type InputType = 'topic' | 'url' | 'file'

interface GenerationProgress {
  status: 'idle' | 'pending' | 'processing' | 'completed' | 'failed'
  progress: number
  currentStep: string
  jobId?: string
  result?: JobStatus['result']
  error?: string
}

export default function GeneratePage() {
  const navigate = useNavigate()
  const [inputType, setInputType] = useState<InputType>('topic')
  const [topic, setTopic] = useState('')
  const [url, setUrl] = useState('')
  const [file, setFile] = useState<File | null>(null)
  const [language, setLanguage] = useState('english')
  const [duration, setDuration] = useState(10)
  const [format, setFormat] = useState('conversation')

  const [generationProgress, setGenerationProgress] = useState<GenerationProgress>({
    status: 'idle',
    progress: 0,
    currentStep: ''
  })
  const [showFeedback, setShowFeedback] = useState(false)

  // WebSocket for real-time progress
  useEffect(() => {
    if (!generationProgress.jobId || generationProgress.status === 'completed' || generationProgress.status === 'failed') {
      return
    }

    const ws = createJobWebSocket(generationProgress.jobId)

    ws.onmessage = (event) => {
      const data = JSON.parse(event.data)
      setGenerationProgress(prev => ({
        ...prev,
        status: data.status,
        progress: data.progress,
        currentStep: data.current_step
      }))

      // If completed, fetch full result
      if (data.status === 'completed' || data.status === 'failed') {
        getJobStatus(generationProgress.jobId!).then(job => {
          setGenerationProgress(prev => ({
            ...prev,
            result: job.result,
            error: job.error
          }))
        })
      }
    }

    ws.onerror = () => {
      // Fallback to polling if WebSocket fails
      const poll = setInterval(async () => {
        if (!generationProgress.jobId) return
        const job = await getJobStatus(generationProgress.jobId)
        setGenerationProgress(prev => ({
          ...prev,
          status: job.status,
          progress: job.progress,
          currentStep: job.current_step,
          result: job.result,
          error: job.error
        }))
        if (job.status === 'completed' || job.status === 'failed') {
          clearInterval(poll)
        }
      }, 2000)
      return () => clearInterval(poll)
    }

    return () => ws.close()
  }, [generationProgress.jobId, generationProgress.status])

  const mutation = useMutation({
    mutationFn: generatePodcast,
    onSuccess: (data) => {
      setGenerationProgress({
        status: 'pending',
        progress: 0,
        currentStep: 'Starting...',
        jobId: data.job_id
      })
    },
    onError: (error) => {
      setGenerationProgress({
        status: 'failed',
        progress: 0,
        currentStep: '',
        error: (error as Error).message
      })
    }
  })

  const handleFeedbackSubmit = async (feedback: FeedbackData) => {
    await submitFeedback({
      job_id: feedback.job_id,
      rating: feedback.rating,
      feedback_type: feedback.feedback_type,
      comments: feedback.comments,
      listen_percentage: feedback.listen_percentage,
      would_share: feedback.would_share,
      aspects: feedback.aspects
    })
  }

  const resetForm = useCallback(() => {
    setGenerationProgress({ status: 'idle', progress: 0, currentStep: '' })
    setTopic('')
    setUrl('')
    setFile(null)
  }, [])

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()

    const request: GenerateRequest = {
      user_request: inputType === 'topic' ? topic : inputType === 'url' ? `Content from ${url}` : `Content from ${file?.name}`,
      contents: [],
      target_language: language,
      target_duration_minutes: duration,
      episode_format: format,
      audience_level: 'intermediate',
    }

    if (inputType === 'topic') {
      request.contents = [{ type: 'topic', source: topic }]
    } else if (inputType === 'url') {
      request.contents = [{ type: 'url', source: url }]
    }

    mutation.mutate(request)
  }

  return (
    <div className="max-w-3xl mx-auto">
      <h1 className="text-3xl font-bold text-gray-900 mb-2">Generate Podcast</h1>
      <p className="text-gray-600 mb-8">
        Provide your content and customize the output settings.
      </p>

      <form onSubmit={handleSubmit} className="space-y-8">
        {/* Input Type Selection */}
        <div className="card">
          <h2 className="text-lg font-semibold text-gray-900 mb-4">Content Source</h2>
          <div className="grid grid-cols-3 gap-4 mb-6">
            {[
              { type: 'topic', label: 'Topic', icon: FileText },
              { type: 'url', label: 'URL', icon: LinkIcon },
              { type: 'file', label: 'File Upload', icon: Upload },
            ].map(({ type, label, icon: Icon }) => (
              <button
                key={type}
                type="button"
                onClick={() => setInputType(type as InputType)}
                className={`p-4 rounded-lg border-2 transition-all ${
                  inputType === type
                    ? 'border-primary-500 bg-primary-50'
                    : 'border-gray-200 hover:border-gray-300'
                }`}
              >
                <Icon className={`w-6 h-6 mx-auto mb-2 ${inputType === type ? 'text-primary-600' : 'text-gray-400'}`} />
                <span className={`text-sm font-medium ${inputType === type ? 'text-primary-700' : 'text-gray-600'}`}>
                  {label}
                </span>
              </button>
            ))}
          </div>

          {/* Input Fields */}
          {inputType === 'topic' && (
            <div>
              <label className="label">What topic would you like a podcast about?</label>
              <textarea
                value={topic}
                onChange={(e) => setTopic(e.target.value)}
                placeholder="e.g., The future of AI in healthcare, Recent developments in renewable energy..."
                className="input min-h-[120px]"
                required
              />
            </div>
          )}

          {inputType === 'url' && (
            <div>
              <label className="label">Article or Website URL</label>
              <input
                type="url"
                value={url}
                onChange={(e) => setUrl(e.target.value)}
                placeholder="https://example.com/article"
                className="input"
                required
              />
            </div>
          )}

          {inputType === 'file' && (
            <div>
              <label className="label">Upload PDF or Audio File</label>
              <div className="border-2 border-dashed border-gray-300 rounded-lg p-8 text-center hover:border-primary-400 transition-colors">
                <input
                  type="file"
                  accept=".pdf,.mp3,.wav,.m4a"
                  onChange={(e) => setFile(e.target.files?.[0] || null)}
                  className="hidden"
                  id="file-upload"
                />
                <label htmlFor="file-upload" className="cursor-pointer">
                  <Upload className="w-10 h-10 text-gray-400 mx-auto mb-2" />
                  <span className="text-gray-600">
                    {file ? file.name : 'Click to upload or drag and drop'}
                  </span>
                  <p className="text-sm text-gray-400 mt-1">PDF, MP3, WAV, M4A</p>
                </label>
              </div>
            </div>
          )}
        </div>

        {/* Settings */}
        <div className="card">
          <h2 className="text-lg font-semibold text-gray-900 mb-4">Settings</h2>
          <div className="grid md:grid-cols-3 gap-6">
            <div>
              <label className="label">Language</label>
              <select
                value={language}
                onChange={(e) => setLanguage(e.target.value)}
                className="input"
              >
                <option value="english">English</option>
                <option value="hindi">Hindi</option>
                <option value="tamil">Tamil</option>
              </select>
            </div>

            <div>
              <label className="label">Duration (minutes)</label>
              <select
                value={duration}
                onChange={(e) => setDuration(Number(e.target.value))}
                className="input"
              >
                <option value={5}>5 minutes</option>
                <option value={10}>10 minutes</option>
                <option value={15}>15 minutes</option>
                <option value={20}>20 minutes</option>
                <option value={30}>30 minutes</option>
              </select>
            </div>

            <div>
              <label className="label">Format</label>
              <select
                value={format}
                onChange={(e) => setFormat(e.target.value)}
                className="input"
              >
                <option value="conversation">Conversation</option>
                <option value="interview">Interview</option>
                <option value="monologue">Monologue</option>
              </select>
            </div>
          </div>
        </div>

        {/* Submit Button */}
        <button
          type="submit"
          disabled={mutation.isPending}
          className="btn btn-primary w-full py-3 text-lg flex items-center justify-center space-x-2"
        >
          {mutation.isPending ? (
            <>
              <Loader2 className="w-5 h-5 animate-spin" />
              <span>Generating...</span>
            </>
          ) : (
            <>
              <span>Generate Podcast</span>
            </>
          )}
        </button>

        {/* Progress Indicator */}
        {(generationProgress.status === 'pending' || generationProgress.status === 'processing') && (
          <div className="card">
            <div className="flex items-center justify-between mb-4">
              <h3 className="font-semibold text-gray-900">Generating Podcast</h3>
              <span className="text-sm text-gray-500">{generationProgress.progress}%</span>
            </div>
            <div className="w-full bg-gray-200 rounded-full h-3 mb-3">
              <div
                className="bg-primary-500 h-3 rounded-full transition-all duration-300"
                style={{ width: `${generationProgress.progress}%` }}
              />
            </div>
            <div className="flex items-center gap-2 text-sm text-gray-600">
              <Loader2 className="w-4 h-4 animate-spin" />
              <span>{generationProgress.currentStep || 'Processing...'}</span>
            </div>
          </div>
        )}

        {/* Success Result */}
        {generationProgress.status === 'completed' && generationProgress.result && (
          <div className="space-y-4">
            <div className="flex items-center space-x-2 text-green-600 bg-green-50 p-4 rounded-lg">
              <CheckCircle2 className="w-5 h-5" />
              <span>Podcast generated successfully!</span>
            </div>

            {/* Quality Score */}
            {generationProgress.result.quality_score && (
              <div className="card">
                <div className="flex items-center justify-between">
                  <span className="text-sm text-gray-600">Quality Score</span>
                  <span className="font-semibold text-primary-600">
                    {(generationProgress.result.quality_score * 100).toFixed(0)}%
                  </span>
                </div>
                {generationProgress.result.fm_reward !== undefined && (
                  <div className="flex items-center justify-between mt-2">
                    <span className="text-sm text-gray-600">FM Reward</span>
                    <span className="font-semibold text-gray-700">
                      {generationProgress.result.fm_reward.toFixed(2)}
                    </span>
                  </div>
                )}
              </div>
            )}

            {/* Audio Player */}
            {generationProgress.result.audio_file_path ? (
              <PodcastPlayer
                jobId={generationProgress.jobId!}
                title={topic || url || file?.name || 'Generated Podcast'}
                audioUrl={`/api/download/${generationProgress.jobId}`}
                durationSeconds={(generationProgress.result.duration_minutes || duration) * 60}
                script={generationProgress.result.final_script}
                onFeedbackSubmit={handleFeedbackSubmit}
              />
            ) : (
              <div className="card">
                <h3 className="font-semibold text-gray-900 mb-3">Generated Script</h3>
                <div className="bg-gray-50 p-4 rounded-lg text-sm text-gray-700 max-h-64 overflow-y-auto whitespace-pre-wrap">
                  {generationProgress.result.final_script || 'No script available'}
                </div>
                <p className="text-xs text-gray-400 mt-2">
                  Audio synthesis was not available. Install VibeVoice or gTTS to enable audio generation.
                </p>
                <button
                  onClick={() => setShowFeedback(true)}
                  className="btn btn-secondary mt-4"
                >
                  Give Feedback
                </button>
              </div>
            )}

            {/* Actions */}
            <div className="flex gap-4">
              <button
                onClick={resetForm}
                className="btn btn-primary flex-1 flex items-center justify-center gap-2"
              >
                <span>Generate Another</span>
                <ArrowRight className="w-4 h-4" />
              </button>
              <button
                onClick={() => navigate('/history')}
                className="btn btn-secondary"
              >
                View History
              </button>
            </div>
          </div>
        )}

        {/* Error */}
        {generationProgress.status === 'failed' && (
          <div className="space-y-4">
            <div className="flex items-center space-x-2 text-red-600 bg-red-50 p-4 rounded-lg">
              <AlertCircle className="w-5 h-5" />
              <span>Error: {generationProgress.error || 'Generation failed'}</span>
            </div>
            <button
              onClick={resetForm}
              className="btn btn-secondary"
            >
              Try Again
            </button>
          </div>
        )}

        {/* Initial Error */}
        {mutation.isError && generationProgress.status === 'idle' && (
          <div className="flex items-center space-x-2 text-red-600 bg-red-50 p-4 rounded-lg">
            <AlertCircle className="w-5 h-5" />
            <span>Error: {(mutation.error as Error).message}</span>
          </div>
        )}
      </form>

      {/* Feedback Modal for script-only results */}
      {showFeedback && generationProgress.jobId && (
        <FeedbackModal
          jobId={generationProgress.jobId}
          isOpen={showFeedback}
          onClose={() => setShowFeedback(false)}
          onSubmit={handleFeedbackSubmit}
        />
      )}
    </div>
  )
}
