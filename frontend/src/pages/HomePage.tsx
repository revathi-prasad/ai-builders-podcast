import { Link } from 'react-router-dom'
import { Mic, FileText, Globe, Headphones, Sparkles, ArrowRight } from 'lucide-react'

const features = [
  {
    icon: FileText,
    title: 'Multi-Modal Input',
    description: 'Upload PDFs, audio files, paste URLs, or just describe a topic',
  },
  {
    icon: Globe,
    title: 'Cultural Adaptation',
    description: 'Generate podcasts in English, Hindi, or Tamil with cultural context',
  },
  {
    icon: Sparkles,
    title: 'AI Verification',
    description: 'Fact-checking and quality verification built into the pipeline',
  },
  {
    icon: Headphones,
    title: 'Natural Voices',
    description: 'Multiple AI host personas with natural conversation flow',
  },
]

export default function HomePage() {
  return (
    <div className="space-y-12">
      {/* Hero Section */}
      <section className="text-center py-12">
        <div className="inline-flex items-center px-4 py-2 bg-primary-50 text-primary-700 rounded-full text-sm font-medium mb-4">
          <Sparkles className="w-4 h-4 mr-2" />
          Multi-Agent System with RL
        </div>
        <h1 className="text-5xl font-bold text-gray-900 mb-4">
          Transform Any Content Into
          <br />
          <span className="bg-gradient-to-r from-primary-600 to-accent-600 bg-clip-text text-transparent">
            Engaging Podcasts
          </span>
        </h1>
        <p className="text-xl text-gray-600 max-w-2xl mx-auto mb-8">
          Upload documents, share URLs, or describe a topic. Our multi-agent AI system
          creates fact-checked, culturally-adapted podcast episodes in minutes.
        </p>
        <div className="flex items-center justify-center gap-4">
          <Link
            to="/generate"
            className="btn btn-primary flex items-center space-x-2 text-lg px-6 py-3"
          >
            <Mic className="w-5 h-5" />
            <span>Start Creating</span>
            <ArrowRight className="w-5 h-5" />
          </Link>
          <Link
            to="/history"
            className="btn btn-secondary flex items-center space-x-2 text-lg px-6 py-3"
          >
            <span>View Examples</span>
          </Link>
        </div>
      </section>

      {/* Features Grid */}
      <section>
        <h2 className="text-2xl font-bold text-gray-900 text-center mb-8">
          Powered by Advanced AI
        </h2>
        <div className="grid md:grid-cols-2 lg:grid-cols-4 gap-6">
          {features.map(({ icon: Icon, title, description }) => (
            <div key={title} className="card hover:shadow-md transition-shadow">
              <div className="w-12 h-12 bg-primary-100 rounded-lg flex items-center justify-center mb-4">
                <Icon className="w-6 h-6 text-primary-600" />
              </div>
              <h3 className="text-lg font-semibold text-gray-900 mb-2">{title}</h3>
              <p className="text-gray-600">{description}</p>
            </div>
          ))}
        </div>
      </section>

      {/* How It Works */}
      <section className="card bg-gradient-to-br from-primary-50 to-accent-50 border-0">
        <h2 className="text-2xl font-bold text-gray-900 text-center mb-8">
          How It Works
        </h2>
        <div className="grid md:grid-cols-4 gap-8">
          {[
            { step: '1', title: 'Upload Content', desc: 'PDFs, audio, URLs, or topics' },
            { step: '2', title: 'AI Processing', desc: 'Multi-agent content extraction' },
            { step: '3', title: 'Script Generation', desc: 'Natural dialogue with citations' },
            { step: '4', title: 'Audio Synthesis', desc: 'High-quality podcast audio' },
          ].map(({ step, title, desc }) => (
            <div key={step} className="text-center">
              <div className="w-12 h-12 bg-white rounded-full flex items-center justify-center mx-auto mb-4 shadow-sm">
                <span className="text-xl font-bold text-primary-600">{step}</span>
              </div>
              <h3 className="font-semibold text-gray-900">{title}</h3>
              <p className="text-sm text-gray-600">{desc}</p>
            </div>
          ))}
        </div>
      </section>
    </div>
  )
}
