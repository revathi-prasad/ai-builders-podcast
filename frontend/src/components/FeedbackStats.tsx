import { useEffect, useState } from 'react'
import { BarChart3, Star, TrendingUp, MessageSquare } from 'lucide-react'
import { getFeedbackStats, type FeedbackStats } from '../api/client'
import { clsx } from 'clsx'

interface FeedbackStatsDisplayProps {
  className?: string
  refreshInterval?: number // ms, 0 to disable
}

export default function FeedbackStatsDisplay({
  className,
  refreshInterval = 30000
}: FeedbackStatsDisplayProps) {
  const [stats, setStats] = useState<FeedbackStats | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const fetchStats = async () => {
    try {
      const data = await getFeedbackStats()
      setStats(data)
      setError(null)
    } catch (err) {
      setError('Failed to load stats')
      console.error(err)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchStats()

    if (refreshInterval > 0) {
      const interval = setInterval(fetchStats, refreshInterval)
      return () => clearInterval(interval)
    }
  }, [refreshInterval])

  if (loading) {
    return (
      <div className={clsx('card animate-pulse', className)}>
        <div className="h-24 bg-gray-100 rounded" />
      </div>
    )
  }

  if (error || !stats) {
    return (
      <div className={clsx('card text-center text-gray-500', className)}>
        <p>{error || 'No feedback data yet'}</p>
      </div>
    )
  }

  const maxRating = Math.max(
    ...Object.values(stats.rating_distribution).map(Number)
  )

  return (
    <div className={clsx('card', className)}>
      <h3 className="font-semibold text-gray-900 mb-4 flex items-center gap-2">
        <BarChart3 className="w-5 h-5 text-primary-600" />
        Feedback Overview
      </h3>

      {/* Summary Stats */}
      <div className="grid grid-cols-3 gap-4 mb-6">
        <div className="text-center p-3 bg-gray-50 rounded-lg">
          <div className="text-2xl font-bold text-gray-900">
            {stats.total_feedback}
          </div>
          <div className="text-xs text-gray-500">Total Responses</div>
        </div>
        <div className="text-center p-3 bg-gray-50 rounded-lg">
          <div className="flex items-center justify-center gap-1">
            <span className="text-2xl font-bold text-gray-900">
              {stats.avg_rating.toFixed(1)}
            </span>
            <Star className="w-5 h-5 text-yellow-400 fill-yellow-400" />
          </div>
          <div className="text-xs text-gray-500">Avg Rating</div>
        </div>
        <div className="text-center p-3 bg-gray-50 rounded-lg">
          <div className="text-2xl font-bold text-gray-900">
            {stats.feedback_by_type.pairwise || 0}
          </div>
          <div className="text-xs text-gray-500">Comparisons</div>
        </div>
      </div>

      {/* Rating Distribution */}
      <div className="space-y-2">
        <h4 className="text-sm font-medium text-gray-700">Rating Distribution</h4>
        {[5, 4, 3, 2, 1].map((rating) => {
          const count = Number(stats.rating_distribution[String(rating)] || 0)
          const percentage = maxRating > 0 ? (count / maxRating) * 100 : 0

          return (
            <div key={rating} className="flex items-center gap-2">
              <div className="flex items-center gap-1 w-12">
                <span className="text-sm text-gray-600">{rating}</span>
                <Star className="w-3 h-3 text-yellow-400 fill-yellow-400" />
              </div>
              <div className="flex-1 h-4 bg-gray-100 rounded-full overflow-hidden">
                <div
                  className="h-full bg-primary-500 rounded-full transition-all duration-500"
                  style={{ width: `${percentage}%` }}
                />
              </div>
              <span className="text-xs text-gray-500 w-8 text-right">
                {count}
              </span>
            </div>
          )
        })}
      </div>

      {/* Feedback Types */}
      {Object.keys(stats.feedback_by_type).length > 1 && (
        <div className="mt-4 pt-4 border-t">
          <h4 className="text-sm font-medium text-gray-700 mb-2">By Type</h4>
          <div className="flex flex-wrap gap-2">
            {Object.entries(stats.feedback_by_type).map(([type, count]) => (
              <span
                key={type}
                className="px-2 py-1 bg-gray-100 rounded text-xs text-gray-600"
              >
                {type}: {count}
              </span>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
