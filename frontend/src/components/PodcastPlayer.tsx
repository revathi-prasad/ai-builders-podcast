import { useState, useRef, useEffect } from 'react'
import {
  Play,
  Pause,
  SkipBack,
  SkipForward,
  Volume2,
  VolumeX,
  MessageSquare,
  Download
} from 'lucide-react'
import { clsx } from 'clsx'
import {
  FeedbackModal,
  useImplicitTracking,
  calculateEngagementScore
} from './feedback'
import type { FeedbackData } from './feedback'

interface PodcastPlayerProps {
  jobId: string
  title: string
  audioUrl?: string
  durationSeconds: number
  script?: string
  onFeedbackSubmit: (feedback: FeedbackData) => Promise<void>
  onDownload?: () => void
}

function formatTime(seconds: number): string {
  const mins = Math.floor(seconds / 60)
  const secs = Math.floor(seconds % 60)
  return `${mins}:${secs.toString().padStart(2, '0')}`
}

export default function PodcastPlayer({
  jobId,
  title,
  audioUrl,
  durationSeconds,
  script,
  onFeedbackSubmit,
  onDownload
}: PodcastPlayerProps) {
  const audioRef = useRef<HTMLAudioElement>(null)
  const [isPlaying, setIsPlaying] = useState(false)
  const [currentTime, setCurrentTime] = useState(0)
  const [volume, setVolume] = useState(1)
  const [isMuted, setIsMuted] = useState(false)
  const [playbackRate, setPlaybackRate] = useState(1)
  const [showFeedbackModal, setShowFeedbackModal] = useState(false)
  const [showScript, setShowScript] = useState(false)

  // Implicit tracking
  const {
    metrics,
    trackPlay,
    trackPause,
    trackSeek,
    trackSpeedChange,
    updatePosition
  } = useImplicitTracking({
    jobId,
    totalDurationSeconds: durationSeconds,
    onComplete: (finalMetrics) => {
      // Show feedback modal when user completes listening
      const engagementScore = calculateEngagementScore(finalMetrics)
      console.log('Listening completed. Engagement score:', engagementScore)
      setTimeout(() => setShowFeedbackModal(true), 1000)
    }
  })

  // Sync audio state
  useEffect(() => {
    const audio = audioRef.current
    if (!audio) return

    const handleTimeUpdate = () => {
      setCurrentTime(audio.currentTime)
      updatePosition(audio.currentTime)
    }

    const handleEnded = () => {
      setIsPlaying(false)
      trackPause()
      setShowFeedbackModal(true)
    }

    audio.addEventListener('timeupdate', handleTimeUpdate)
    audio.addEventListener('ended', handleEnded)

    return () => {
      audio.removeEventListener('timeupdate', handleTimeUpdate)
      audio.removeEventListener('ended', handleEnded)
    }
  }, [updatePosition, trackPause])

  const togglePlay = () => {
    const audio = audioRef.current
    if (!audio) return

    if (isPlaying) {
      audio.pause()
      trackPause()
    } else {
      audio.play()
      trackPlay()
    }
    setIsPlaying(!isPlaying)
  }

  const handleSeek = (e: React.ChangeEvent<HTMLInputElement>) => {
    const audio = audioRef.current
    if (!audio) return

    const newTime = parseFloat(e.target.value)
    audio.currentTime = newTime
    setCurrentTime(newTime)
    trackSeek(newTime)
  }

  const skip = (seconds: number) => {
    const audio = audioRef.current
    if (!audio) return

    const newTime = Math.max(0, Math.min(audio.currentTime + seconds, durationSeconds))
    audio.currentTime = newTime
    setCurrentTime(newTime)
    trackSeek(newTime)
  }

  const toggleMute = () => {
    const audio = audioRef.current
    if (!audio) return

    audio.muted = !isMuted
    setIsMuted(!isMuted)
  }

  const handleVolumeChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const audio = audioRef.current
    if (!audio) return

    const newVolume = parseFloat(e.target.value)
    audio.volume = newVolume
    setVolume(newVolume)
    setIsMuted(newVolume === 0)
  }

  const handlePlaybackRateChange = (rate: number) => {
    const audio = audioRef.current
    if (!audio) return

    audio.playbackRate = rate
    setPlaybackRate(rate)
    trackSpeedChange(rate)
  }

  const handleFeedbackSubmit = async (feedback: FeedbackData) => {
    // Enrich with implicit metrics
    const enrichedFeedback: FeedbackData = {
      ...feedback,
      listen_percentage: metrics.listenPercentage
    }
    await onFeedbackSubmit(enrichedFeedback)
  }

  const progress = durationSeconds > 0 ? (currentTime / durationSeconds) * 100 : 0

  return (
    <div className="card">
      {/* Hidden audio element */}
      {audioUrl && (
        <audio ref={audioRef} src={audioUrl} preload="metadata" />
      )}

      {/* Title */}
      <div className="flex items-center justify-between mb-4">
        <h3 className="font-semibold text-gray-900 truncate">{title}</h3>
        <div className="flex items-center gap-2">
          {onDownload && (
            <button
              onClick={onDownload}
              className="p-2 text-gray-400 hover:text-gray-600 transition-colors"
              title="Download"
            >
              <Download className="w-5 h-5" />
            </button>
          )}
          <button
            onClick={() => setShowFeedbackModal(true)}
            className="p-2 text-gray-400 hover:text-primary-600 transition-colors"
            title="Give feedback"
          >
            <MessageSquare className="w-5 h-5" />
          </button>
        </div>
      </div>

      {/* Progress bar */}
      <div className="mb-4">
        <input
          type="range"
          min={0}
          max={durationSeconds}
          value={currentTime}
          onChange={handleSeek}
          className="w-full h-2 bg-gray-200 rounded-lg appearance-none cursor-pointer accent-primary-600"
          style={{
            background: `linear-gradient(to right, rgb(var(--color-primary-600)) ${progress}%, rgb(229, 231, 235) ${progress}%)`
          }}
        />
        <div className="flex justify-between text-xs text-gray-500 mt-1">
          <span>{formatTime(currentTime)}</span>
          <span>{formatTime(durationSeconds)}</span>
        </div>
      </div>

      {/* Controls */}
      <div className="flex items-center justify-between">
        {/* Playback controls */}
        <div className="flex items-center gap-2">
          <button
            onClick={() => skip(-10)}
            className="p-2 text-gray-600 hover:text-gray-900 transition-colors"
            title="Skip back 10s"
          >
            <SkipBack className="w-5 h-5" />
          </button>

          <button
            onClick={togglePlay}
            className="w-12 h-12 bg-primary-600 hover:bg-primary-700 text-white rounded-full flex items-center justify-center transition-colors"
          >
            {isPlaying ? (
              <Pause className="w-6 h-6" />
            ) : (
              <Play className="w-6 h-6 ml-0.5" />
            )}
          </button>

          <button
            onClick={() => skip(30)}
            className="p-2 text-gray-600 hover:text-gray-900 transition-colors"
            title="Skip forward 30s"
          >
            <SkipForward className="w-5 h-5" />
          </button>
        </div>

        {/* Speed control */}
        <div className="flex items-center gap-1">
          {[0.5, 1, 1.5, 2].map((rate) => (
            <button
              key={rate}
              onClick={() => handlePlaybackRateChange(rate)}
              className={clsx(
                'px-2 py-1 text-xs rounded transition-colors',
                playbackRate === rate
                  ? 'bg-primary-100 text-primary-700 font-medium'
                  : 'text-gray-500 hover:bg-gray-100'
              )}
            >
              {rate}x
            </button>
          ))}
        </div>

        {/* Volume control */}
        <div className="flex items-center gap-2">
          <button
            onClick={toggleMute}
            className="p-2 text-gray-600 hover:text-gray-900 transition-colors"
          >
            {isMuted || volume === 0 ? (
              <VolumeX className="w-5 h-5" />
            ) : (
              <Volume2 className="w-5 h-5" />
            )}
          </button>
          <input
            type="range"
            min={0}
            max={1}
            step={0.1}
            value={isMuted ? 0 : volume}
            onChange={handleVolumeChange}
            className="w-20 h-1.5 bg-gray-200 rounded-lg appearance-none cursor-pointer accent-primary-600"
          />
        </div>
      </div>

      {/* Listen stats (subtle) */}
      {metrics.listenPercentage > 0 && (
        <div className="mt-4 pt-4 border-t text-xs text-gray-400 flex items-center justify-between">
          <span>{metrics.listenPercentage}% listened</span>
          {metrics.pauseCount > 0 && (
            <span>{metrics.pauseCount} pause{metrics.pauseCount > 1 ? 's' : ''}</span>
          )}
        </div>
      )}

      {/* Script toggle */}
      {script && (
        <div className="mt-4 pt-4 border-t">
          <button
            onClick={() => setShowScript(!showScript)}
            className="text-sm text-primary-600 hover:text-primary-700"
          >
            {showScript ? 'Hide script' : 'Show script'}
          </button>
          {showScript && (
            <div className="mt-3 p-4 bg-gray-50 rounded-lg text-sm text-gray-700 max-h-48 overflow-y-auto">
              {script}
            </div>
          )}
        </div>
      )}

      {/* Feedback Modal */}
      <FeedbackModal
        jobId={jobId}
        isOpen={showFeedbackModal}
        onClose={() => setShowFeedbackModal(false)}
        onSubmit={handleFeedbackSubmit}
        listenPercentage={metrics.listenPercentage}
      />
    </div>
  )
}
