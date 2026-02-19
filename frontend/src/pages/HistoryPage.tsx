import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Clock, CheckCircle2, Loader2, AlertCircle, Play, Download, MessageSquare, Star } from 'lucide-react'
import { getJobs, submitFeedback, type JobStatus } from '../api/client'
import { clsx } from 'clsx'
import { FeedbackModal, FeedbackStats } from '../components'
import type { FeedbackData } from '../components'

const statusConfig = {
  pending: { icon: Clock, color: 'text-yellow-500', bg: 'bg-yellow-50' },
  processing: { icon: Loader2, color: 'text-blue-500', bg: 'bg-blue-50', animate: true },
  completed: { icon: CheckCircle2, color: 'text-green-500', bg: 'bg-green-50' },
  failed: { icon: AlertCircle, color: 'text-red-500', bg: 'bg-red-50' },
}

export default function HistoryPage() {
  const [feedbackJobId, setFeedbackJobId] = useState<string | null>(null)

  const { data, isLoading, error } = useQuery({
    queryKey: ['jobs'],
    queryFn: getJobs,
    refetchInterval: 5000, // Refresh every 5 seconds
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

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-12">
        <Loader2 className="w-8 h-8 animate-spin text-primary-500" />
      </div>
    )
  }

  if (error) {
    return (
      <div className="text-center py-12">
        <AlertCircle className="w-12 h-12 text-red-400 mx-auto mb-4" />
        <p className="text-gray-600">Failed to load history</p>
      </div>
    )
  }

  const jobs = data?.jobs || []

  return (
    <div className="grid lg:grid-cols-3 gap-8">
      {/* Main Content */}
      <div className="lg:col-span-2">
        <div className="flex items-center justify-between mb-8">
          <div>
            <h1 className="text-3xl font-bold text-gray-900">Generation History</h1>
            <p className="text-gray-600">Track your podcast generation jobs</p>
          </div>
          <span className="text-sm text-gray-500">{jobs.length} jobs</span>
        </div>

      {jobs.length === 0 ? (
        <div className="card text-center py-12">
          <Clock className="w-12 h-12 text-gray-300 mx-auto mb-4" />
          <h3 className="text-lg font-medium text-gray-900 mb-2">No podcasts yet</h3>
          <p className="text-gray-500">Your generated podcasts will appear here</p>
        </div>
      ) : (
        <div className="space-y-4">
          {jobs.map((job: JobStatus) => {
            const status = statusConfig[job.status as keyof typeof statusConfig]
            const StatusIcon = status.icon

            return (
              <div key={job.job_id} className="card hover:shadow-md transition-shadow">
                <div className="flex items-start justify-between">
                  <div className="flex items-start space-x-4">
                    <div className={clsx('p-2 rounded-lg', status.bg)}>
                      <StatusIcon
                        className={clsx('w-5 h-5', status.color, status.animate && 'animate-spin')}
                      />
                    </div>
                    <div>
                      <h3 className="font-medium text-gray-900">
                        Job {job.job_id.slice(0, 8)}...
                      </h3>
                      <p className="text-sm text-gray-500 mt-1">
                        {job.current_step}
                      </p>
                      <p className="text-xs text-gray-400 mt-2">
                        Created: {new Date(job.created_at).toLocaleString()}
                      </p>
                    </div>
                  </div>

                  <div className="flex items-center space-x-2">
                    {job.status === 'processing' && (
                      <div className="flex items-center space-x-2 text-sm text-gray-500">
                        <div className="w-24 bg-gray-200 rounded-full h-2">
                          <div
                            className="bg-primary-500 h-2 rounded-full transition-all"
                            style={{ width: `${job.progress}%` }}
                          />
                        </div>
                        <span>{job.progress}%</span>
                      </div>
                    )}

                    {job.status === 'completed' && (
                      <div className="flex items-center space-x-2">
                        {job.result?.quality_score && (
                          <div className="flex items-center gap-1 text-sm text-gray-500 mr-2">
                            <Star className="w-4 h-4 text-yellow-400 fill-yellow-400" />
                            <span>{(job.result.quality_score * 100).toFixed(0)}%</span>
                          </div>
                        )}
                        <button className="btn btn-secondary flex items-center space-x-1 text-sm">
                          <Play className="w-4 h-4" />
                          <span>Play</span>
                        </button>
                        <button className="btn btn-secondary flex items-center space-x-1 text-sm">
                          <Download className="w-4 h-4" />
                          <span>Download</span>
                        </button>
                        <button
                          onClick={() => setFeedbackJobId(job.job_id)}
                          className="btn btn-secondary flex items-center space-x-1 text-sm"
                        >
                          <MessageSquare className="w-4 h-4" />
                          <span>Feedback</span>
                        </button>
                      </div>
                    )}

                    {job.status === 'failed' && (
                      <span className="text-sm text-red-500">
                        {job.error || 'Generation failed'}
                      </span>
                    )}
                  </div>
                </div>
              </div>
            )
          })}
        </div>
      )}
      </div>

      {/* Sidebar */}
      <div className="space-y-6">
        <FeedbackStats />

        {/* Quick Actions */}
        <div className="card">
          <h3 className="font-semibold text-gray-900 mb-3">Quick Tips</h3>
          <ul className="text-sm text-gray-600 space-y-2">
            <li className="flex items-start gap-2">
              <Star className="w-4 h-4 text-yellow-400 mt-0.5 flex-shrink-0" />
              <span>Rate podcasts to help improve our AI</span>
            </li>
            <li className="flex items-start gap-2">
              <MessageSquare className="w-4 h-4 text-primary-500 mt-0.5 flex-shrink-0" />
              <span>Detailed feedback helps us learn what works best</span>
            </li>
          </ul>
        </div>
      </div>

      {/* Feedback Modal */}
      {feedbackJobId && (
        <FeedbackModal
          jobId={feedbackJobId}
          isOpen={true}
          onClose={() => setFeedbackJobId(null)}
          onSubmit={handleFeedbackSubmit}
        />
      )}
    </div>
  )
}
