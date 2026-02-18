import { useState } from 'react'
import { X, MessageSquare, ThumbsUp, ThumbsDown } from 'lucide-react'
import { clsx } from 'clsx'
import StarRating from './StarRating'

interface FeedbackModalProps {
  jobId: string
  isOpen: boolean
  onClose: () => void
  onSubmit: (feedback: FeedbackData) => Promise<void>
  listenPercentage?: number
}

export interface FeedbackData {
  job_id: string
  rating: number
  feedback_type: 'explicit' | 'pairwise' | 'implicit'
  comments?: string
  listen_percentage?: number
  would_share?: boolean
  aspects?: {
    content_quality: number
    audio_quality: number
    engagement: number
    accuracy: number
  }
}

const aspectLabels = {
  content_quality: 'Content Quality',
  audio_quality: 'Audio Quality',
  engagement: 'Engagement',
  accuracy: 'Accuracy'
}

export default function FeedbackModal({
  jobId,
  isOpen,
  onClose,
  onSubmit,
  listenPercentage = 0
}: FeedbackModalProps) {
  const [rating, setRating] = useState(0)
  const [comments, setComments] = useState('')
  const [wouldShare, setWouldShare] = useState<boolean | null>(null)
  const [aspects, setAspects] = useState({
    content_quality: 0,
    audio_quality: 0,
    engagement: 0,
    accuracy: 0
  })
  const [showAspects, setShowAspects] = useState(false)
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [submitted, setSubmitted] = useState(false)

  if (!isOpen) return null

  const handleSubmit = async () => {
    if (rating === 0) return

    setIsSubmitting(true)
    try {
      await onSubmit({
        job_id: jobId,
        rating,
        feedback_type: 'explicit',
        comments: comments || undefined,
        listen_percentage: listenPercentage,
        would_share: wouldShare ?? undefined,
        aspects: showAspects ? aspects : undefined
      })
      setSubmitted(true)
      setTimeout(() => {
        onClose()
        // Reset state
        setRating(0)
        setComments('')
        setWouldShare(null)
        setAspects({ content_quality: 0, audio_quality: 0, engagement: 0, accuracy: 0 })
        setShowAspects(false)
        setSubmitted(false)
      }, 1500)
    } catch (error) {
      console.error('Failed to submit feedback:', error)
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
      <div className="bg-white rounded-xl shadow-xl max-w-md w-full mx-4 overflow-hidden">
        {/* Header */}
        <div className="flex items-center justify-between p-4 border-b">
          <h3 className="text-lg font-semibold text-gray-900">
            How was this podcast?
          </h3>
          <button
            onClick={onClose}
            className="text-gray-400 hover:text-gray-600 transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Content */}
        <div className="p-6 space-y-6">
          {submitted ? (
            <div className="text-center py-8">
              <div className="w-16 h-16 bg-green-100 rounded-full flex items-center justify-center mx-auto mb-4">
                <ThumbsUp className="w-8 h-8 text-green-600" />
              </div>
              <h4 className="text-lg font-medium text-gray-900">Thank you!</h4>
              <p className="text-gray-600 mt-1">
                Your feedback helps us improve.
              </p>
            </div>
          ) : (
            <>
              {/* Overall Rating */}
              <div className="text-center">
                <p className="text-sm text-gray-600 mb-3">Overall Rating</p>
                <div className="flex justify-center">
                  <StarRating
                    value={rating}
                    onChange={setRating}
                    size="lg"
                  />
                </div>
                {rating > 0 && (
                  <p className="text-sm text-gray-500 mt-2">
                    {rating === 1 && 'Poor'}
                    {rating === 2 && 'Fair'}
                    {rating === 3 && 'Good'}
                    {rating === 4 && 'Very Good'}
                    {rating === 5 && 'Excellent'}
                  </p>
                )}
              </div>

              {/* Would Share */}
              <div className="flex items-center justify-center gap-4">
                <p className="text-sm text-gray-600">Would you share this?</p>
                <div className="flex gap-2">
                  <button
                    onClick={() => setWouldShare(true)}
                    className={clsx(
                      'p-2 rounded-lg border transition-colors',
                      wouldShare === true
                        ? 'border-green-500 bg-green-50 text-green-600'
                        : 'border-gray-200 hover:border-gray-300 text-gray-400'
                    )}
                  >
                    <ThumbsUp className="w-5 h-5" />
                  </button>
                  <button
                    onClick={() => setWouldShare(false)}
                    className={clsx(
                      'p-2 rounded-lg border transition-colors',
                      wouldShare === false
                        ? 'border-red-500 bg-red-50 text-red-600'
                        : 'border-gray-200 hover:border-gray-300 text-gray-400'
                    )}
                  >
                    <ThumbsDown className="w-5 h-5" />
                  </button>
                </div>
              </div>

              {/* Detailed Aspects (Expandable) */}
              <div>
                <button
                  onClick={() => setShowAspects(!showAspects)}
                  className="text-sm text-primary-600 hover:text-primary-700 flex items-center gap-1"
                >
                  <span>{showAspects ? 'Hide' : 'Rate'} specific aspects</span>
                </button>

                {showAspects && (
                  <div className="mt-4 space-y-3">
                    {(Object.keys(aspects) as Array<keyof typeof aspects>).map((key) => (
                      <div key={key} className="flex items-center justify-between">
                        <span className="text-sm text-gray-600">
                          {aspectLabels[key]}
                        </span>
                        <StarRating
                          value={aspects[key]}
                          onChange={(val) => setAspects({ ...aspects, [key]: val })}
                          size="sm"
                        />
                      </div>
                    ))}
                  </div>
                )}
              </div>

              {/* Comments */}
              <div>
                <label className="flex items-center gap-2 text-sm text-gray-600 mb-2">
                  <MessageSquare className="w-4 h-4" />
                  Additional comments (optional)
                </label>
                <textarea
                  value={comments}
                  onChange={(e) => setComments(e.target.value)}
                  placeholder="What did you like? What could be improved?"
                  className="w-full p-3 border rounded-lg text-sm resize-none focus:ring-2 focus:ring-primary-500 focus:border-transparent"
                  rows={3}
                />
              </div>

              {/* Listen Stats */}
              {listenPercentage > 0 && (
                <div className="text-xs text-gray-400 text-center">
                  You listened to {listenPercentage}% of this episode
                </div>
              )}
            </>
          )}
        </div>

        {/* Footer */}
        {!submitted && (
          <div className="flex justify-end gap-3 p-4 border-t bg-gray-50">
            <button
              onClick={onClose}
              className="px-4 py-2 text-sm text-gray-600 hover:text-gray-800 transition-colors"
            >
              Skip
            </button>
            <button
              onClick={handleSubmit}
              disabled={rating === 0 || isSubmitting}
              className={clsx(
                'px-6 py-2 rounded-lg text-sm font-medium transition-colors',
                rating === 0 || isSubmitting
                  ? 'bg-gray-200 text-gray-400 cursor-not-allowed'
                  : 'bg-primary-600 text-white hover:bg-primary-700'
              )}
            >
              {isSubmitting ? 'Submitting...' : 'Submit'}
            </button>
          </div>
        )}
      </div>
    </div>
  )
}
