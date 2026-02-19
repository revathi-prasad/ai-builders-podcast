import { Outlet, Link, useLocation } from 'react-router-dom'
import { Mic, Home, PlusCircle, History } from 'lucide-react'
import { clsx } from 'clsx'

const navItems = [
  { path: '/', label: 'Home', icon: Home },
  { path: '/generate', label: 'Generate', icon: PlusCircle },
  { path: '/history', label: 'History', icon: History },
]

export default function Layout() {
  const location = useLocation()

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <header className="bg-white border-b border-gray-200">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-center justify-between h-16">
            {/* Logo */}
            <Link to="/" className="flex items-center space-x-2">
              <div className="w-10 h-10 bg-gradient-to-br from-primary-500 to-accent-500 rounded-lg flex items-center justify-center">
                <Mic className="w-6 h-6 text-white" />
              </div>
              <span className="text-xl font-bold bg-gradient-to-r from-primary-600 to-accent-600 bg-clip-text text-transparent">
                AI Podcast Generator
              </span>
            </Link>

            {/* Navigation */}
            <nav className="flex items-center space-x-1">
              {navItems.map(({ path, label, icon: Icon }) => (
                <Link
                  key={path}
                  to={path}
                  className={clsx(
                    'flex items-center space-x-2 px-4 py-2 rounded-lg transition-colors',
                    location.pathname === path
                      ? 'bg-primary-50 text-primary-700'
                      : 'text-gray-600 hover:bg-gray-100'
                  )}
                >
                  <Icon className="w-5 h-5" />
                  <span className="font-medium">{label}</span>
                </Link>
              ))}
            </nav>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <Outlet />
      </main>

      {/* Footer */}
      <footer className="bg-white border-t border-gray-200 mt-auto">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4">
          <p className="text-center text-sm text-gray-500">
            AI Podcast Generator v2.0 - Multi-Agent System with RL
          </p>
        </div>
      </footer>
    </div>
  )
}
