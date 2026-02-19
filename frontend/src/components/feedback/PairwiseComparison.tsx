import { useState } from 'react'
import { Play, Pause, Check, X } from 'lucide-react'
import { clsx } from 'clsx'

interface PodcastOption {
  id: string
  title: string
  audioUrl?: string
  script?: string
  duration?: string
}

interface PairwiseComparisonProps {
  optionA: PodcastOption
  optionB: PodcastOption
  onSelect: (winnerId: string, loserId: string) => Promise<void>
  onSkip?: () => void
}

export default function PairwiseComparison({
  optionA,
  optionB,
  onSelect,
  onSkip
}: PairwiseComparisonProps) {
  const [playingId, setPlayingId] = useState<string | null>(null)
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [submitted, setSubmitted] = useState(false)

  const handlePlay = (id: string) => {
    setPlayingId(playingId === id ? null : id)
    // In a real implementation, this would control audio playback
  }

  const handleSelect = async (winnerId: string) => {
    setSelectedId(winnerId)
    setIsSubmitting(true)

    const loserId = winnerId === optionA.id ? optionB.id : optionA.id

    try {
      await onSelect(winnerId, loserId)
      setSubmitted(true)
    } catch (error) {
      console.error('Failed to submit comparison:', error)
      setSelectedId(null)
    } finally {
      setIsSubmitting(false)
    }
  }

  if (submitted) {
    return (
      <div className="card text-center py-8">
        <div className="w-16 h-16 bg-green-100 rounded-full flex items-center justify-center mx-auto mb-4">
          <Check className="w-8 h-8 text-green-600" />
        </div>
        <h4 className="text-lg font-medium text-gray-900">Thanks for comparing!</h4>
        <p className="text-gray-600 mt-1">
          Your preference helps train our AI.
        </p>
      </div>
    )
  }

  return (
    <div className="card">
      <div className="text-center mb-6">
        <h3 className="text-lg font-semibold text-gray-900">
          Which podcast is better?
        </h3>
        <p className="text-sm text-gray-600 mt-1">
          Listen to both and pick your favorite
        </p>
      </div>

      <div className="grid md:grid-cols-2 gap-4">
        {[optionA, optionB].map((option, index) => (
          <div
            key={option.id}
            className={clsx(
              'relative border-2 rounded-xl p-4 transition-all cursor-pointer',
              selectedId === option.id
                ? 'border-primary-500 bg-primary-50'
                : 'border-gray-200 hover:border-gray-300',
              isSubmitting && selectedId !== option.id && 'opacity-50'
            )}
            onClick={() => !isSubmitting && handleSelect(option.id)}
          >
            {/* Label */}
            <div className="absolute -top-3 left-4 bg-white px-2">
              <span className="text-sm font-medium text-gray-500">
                Option {index === 0 ? 'A' : 'B'}
              </span>
            </div>

            {/* Content */}
            <div className="mt-2">
              <h4 className="font-medium text-gray-900 mb-2">
                {option.title}
              </h4>

              {/* Audio Player */}
              {option.audioUrl && (
                <div className="flex items-center gap-3 mb-3">
                  <button
                    onClick={(e) => {
                      e.stopPropagation()
                      handlePlay(option.id)
                    }}
                    className={clsx(
                      'w-10 h-10 rounded-full flex items-center justify-center transition-colors',
                      playingId === option.id
                        ? 'bg-primary-600 text-white'
                        : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
                    )}
                  >
                    {playingId === option.id ? (
                      <Pause className="w-5 h-5" />
                    ) : (
                      <Play className="w-5 h-5 ml-0.5" />
                    )}
                  </button>
                  <div className="flex-1">
                    <div className="h-1 bg-gray-200 rounded-full">
                      <div
                        className="h-full bg-primary-500 rounded-full"
                        style={{ width: playingId === option.id ? '35%' : '0%' }}
                      />
                    </div>
                  </div>
                  <span className="text-xs text-gray-500">
                    {option.duration || '0:00'}
                  </span>
                </div>
              )}

              {/* Script Preview */}
              {option.script && (
                <p className="text-sm text-gray-600 line-clamp-3">
                  {option.script}
                </p>
              )}

              {/* Selection Indicator */}
              {selectedId === option.id && (
                <div className="absolute top-2 right-2">
                  <div className="w-6 h-6 bg-primary-500 rounded-full flex items-center justify-center">
                    <Check className="w-4 h-4 text-white" />
                  </div>
                </div>
              )}
            </div>
          </div>
        ))}
      </div>

      {/* Actions */}
      <div className="flex justify-center mt-6 gap-4">
        <button
          onClick={() => handleSelect(optionA.id)}
          disabled={isSubmitting}
          className={clsx(
            'px-6 py-2 rounded-lg text-sm font-medium transition-colors',
            isSubmitting
              ? 'bg-gray-100 text-gray-400'
              : 'bg-primary-600 text-white hover:bg-primary-700'
          )}
        >
          Prefer A
        </button>
        <button
          onClick={onSkip}
          disabled={isSubmitting}
          className="px-6 py-2 rounded-lg text-sm text-gray-600 hover:bg-gray-100 transition-colors"
        >
          Both are equal
        </button>
        <button
          onClick={() => handleSelect(optionB.id)}
          disabled={isSubmitting}
          className={clsx(
            'px-6 py-2 rounded-lg text-sm font-medium transition-colors',
            isSubmitting
              ? 'bg-gray-100 text-gray-400'
              : 'bg-primary-600 text-white hover:bg-primary-700'
          )}
        >
          Prefer B
        </button>
      </div>

      {/* Skip */}
      {onSkip && (
        <div className="text-center mt-4">
          <button
            onClick={onSkip}
            className="text-sm text-gray-400 hover:text-gray-600"
          >
            Skip comparison
          </button>
        </div>
      )}
    </div>
  )
}
