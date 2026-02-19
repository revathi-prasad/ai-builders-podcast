import { useState } from 'react'
import { Star } from 'lucide-react'
import { clsx } from 'clsx'

interface StarRatingProps {
  value: number
  onChange: (rating: number) => void
  size?: 'sm' | 'md' | 'lg'
  disabled?: boolean
}

const sizeClasses = {
  sm: 'w-5 h-5',
  md: 'w-7 h-7',
  lg: 'w-9 h-9'
}

export default function StarRating({
  value,
  onChange,
  size = 'md',
  disabled = false
}: StarRatingProps) {
  const [hoverValue, setHoverValue] = useState<number | null>(null)

  const displayValue = hoverValue !== null ? hoverValue : value

  return (
    <div className="flex items-center gap-1">
      {[1, 2, 3, 4, 5].map((star) => (
        <button
          key={star}
          type="button"
          onClick={() => !disabled && onChange(star)}
          onMouseEnter={() => !disabled && setHoverValue(star)}
          onMouseLeave={() => setHoverValue(null)}
          disabled={disabled}
          className={clsx(
            'transition-transform',
            !disabled && 'hover:scale-110 cursor-pointer',
            disabled && 'cursor-not-allowed opacity-60'
          )}
          aria-label={`Rate ${star} star${star > 1 ? 's' : ''}`}
        >
          <Star
            className={clsx(
              sizeClasses[size],
              'transition-colors',
              star <= displayValue
                ? 'fill-yellow-400 text-yellow-400'
                : 'fill-gray-200 text-gray-200'
            )}
          />
        </button>
      ))}
    </div>
  )
}
