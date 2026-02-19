import { useEffect, useRef, useCallback, useState } from 'react'

interface ImplicitMetrics {
  jobId: string
  listenDurationSeconds: number
  totalDurationSeconds: number
  listenPercentage: number
  completedListening: boolean
  pauseCount: number
  seekCount: number
  seekBackCount: number
  playbackSpeed: number
  sessionStartTime: string
  sessionEndTime?: string
}

interface UseImplicitTrackingOptions {
  jobId: string
  totalDurationSeconds: number
  onMetricsUpdate?: (metrics: ImplicitMetrics) => void
  onComplete?: (metrics: ImplicitMetrics) => void
  completionThreshold?: number // Default 90%
}

/**
 * Hook for tracking implicit user feedback signals
 *
 * Tracks:
 * - Listen duration and completion percentage
 * - Pause events (frustration or distraction signal)
 * - Seek events (engagement or confusion signal)
 * - Playback speed changes
 * - Session timing
 */
export function useImplicitTracking({
  jobId,
  totalDurationSeconds,
  onMetricsUpdate,
  onComplete,
  completionThreshold = 90
}: UseImplicitTrackingOptions) {
  const [isTracking, setIsTracking] = useState(false)
  const [metrics, setMetrics] = useState<ImplicitMetrics>({
    jobId,
    listenDurationSeconds: 0,
    totalDurationSeconds,
    listenPercentage: 0,
    completedListening: false,
    pauseCount: 0,
    seekCount: 0,
    seekBackCount: 0,
    playbackSpeed: 1,
    sessionStartTime: new Date().toISOString()
  })

  const metricsRef = useRef(metrics)
  const lastPositionRef = useRef(0)
  const isPlayingRef = useRef(false)
  const trackingIntervalRef = useRef<number | null>(null)

  // Keep metricsRef in sync
  useEffect(() => {
    metricsRef.current = metrics
  }, [metrics])

  // Start tracking
  const startTracking = useCallback(() => {
    setIsTracking(true)
    setMetrics((prev) => ({
      ...prev,
      sessionStartTime: new Date().toISOString()
    }))
  }, [])

  // Stop tracking
  const stopTracking = useCallback(() => {
    setIsTracking(false)
    if (trackingIntervalRef.current) {
      clearInterval(trackingIntervalRef.current)
      trackingIntervalRef.current = null
    }

    const finalMetrics = {
      ...metricsRef.current,
      sessionEndTime: new Date().toISOString()
    }

    setMetrics(finalMetrics)

    if (onComplete && finalMetrics.listenPercentage >= completionThreshold) {
      onComplete(finalMetrics)
    }
  }, [onComplete, completionThreshold])

  // Track play event
  const trackPlay = useCallback(() => {
    isPlayingRef.current = true

    // Start interval to track listen duration
    if (!trackingIntervalRef.current) {
      trackingIntervalRef.current = window.setInterval(() => {
        if (isPlayingRef.current) {
          setMetrics((prev) => {
            const newDuration = prev.listenDurationSeconds + 1
            const newPercentage = Math.min(
              100,
              Math.round((newDuration / totalDurationSeconds) * 100)
            )
            const newMetrics = {
              ...prev,
              listenDurationSeconds: newDuration,
              listenPercentage: newPercentage,
              completedListening: newPercentage >= completionThreshold
            }

            if (onMetricsUpdate) {
              onMetricsUpdate(newMetrics)
            }

            return newMetrics
          })
        }
      }, 1000)
    }
  }, [totalDurationSeconds, completionThreshold, onMetricsUpdate])

  // Track pause event
  const trackPause = useCallback(() => {
    isPlayingRef.current = false
    setMetrics((prev) => ({
      ...prev,
      pauseCount: prev.pauseCount + 1
    }))
  }, [])

  // Track seek event
  const trackSeek = useCallback((newPosition: number) => {
    const wasSeekBack = newPosition < lastPositionRef.current
    lastPositionRef.current = newPosition

    setMetrics((prev) => ({
      ...prev,
      seekCount: prev.seekCount + 1,
      seekBackCount: wasSeekBack ? prev.seekBackCount + 1 : prev.seekBackCount
    }))
  }, [])

  // Track playback speed change
  const trackSpeedChange = useCallback((speed: number) => {
    setMetrics((prev) => ({
      ...prev,
      playbackSpeed: speed
    }))
  }, [])

  // Update current position (for accurate seek tracking)
  const updatePosition = useCallback((position: number) => {
    lastPositionRef.current = position
  }, [])

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (trackingIntervalRef.current) {
        clearInterval(trackingIntervalRef.current)
      }
    }
  }, [])

  return {
    metrics,
    isTracking,
    startTracking,
    stopTracking,
    trackPlay,
    trackPause,
    trackSeek,
    trackSpeedChange,
    updatePosition
  }
}

/**
 * Calculate engagement score from implicit metrics
 *
 * Higher score = more engaged user
 * Score range: 0-100
 */
export function calculateEngagementScore(metrics: ImplicitMetrics): number {
  let score = 0

  // Completion is the strongest signal (0-50 points)
  score += metrics.listenPercentage * 0.5

  // Low pause count is good (0-20 points)
  const pausePenalty = Math.min(metrics.pauseCount * 4, 20)
  score += 20 - pausePenalty

  // Some seeking is normal, excessive seeking is bad (0-15 points)
  const seekPenalty = Math.min(metrics.seekCount * 2, 15)
  score += 15 - seekPenalty

  // Seek backs often indicate confusion or dislike (0-15 points)
  const seekBackPenalty = Math.min(metrics.seekBackCount * 5, 15)
  score += 15 - seekBackPenalty

  // Speed adjustments (slight bonus for normal speed)
  if (metrics.playbackSpeed === 1) {
    // Normal speed - no adjustment
  } else if (metrics.playbackSpeed > 1 && metrics.playbackSpeed <= 1.5) {
    // Slightly faster - user is engaged but efficient
    score += 2
  } else if (metrics.playbackSpeed > 1.5) {
    // Much faster - user might be rushing through
    score -= 5
  } else if (metrics.playbackSpeed < 1) {
    // Slower - might be struggling with content
    score -= 3
  }

  return Math.max(0, Math.min(100, Math.round(score)))
}

export default useImplicitTracking
