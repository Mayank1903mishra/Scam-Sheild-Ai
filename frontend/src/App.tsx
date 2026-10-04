import { useState } from 'react'
import type { ScanResponse } from './types'
import { InputPage } from './pages/InputPage'
import { ResultPage } from './pages/ResultPage'
import { HistoryPage } from './pages/HistoryPage'

type View =
  | { name: 'input' }
  | { name: 'result'; scan: ScanResponse; origin: 'fresh' | 'history' }
  | { name: 'history' }

export default function App() {
  const [view, setView] = useState<View>({ name: 'input' })

  const goInput = () => setView({ name: 'input' })
  const goHistory = () => setView({ name: 'history' })

  return (
    <div className="app">
      <header className="app-header">
        <div className="app-header__brand">
          <span className="app-header__logo" aria-hidden="true">
            &#128737;
          </span>
          <span className="app-header__title">ScamShield AI</span>
        </div>
        <nav className="app-header__nav" aria-label="Main navigation">
          <button
            type="button"
            className={`nav-button ${view.name === 'input' ? 'nav-button--active' : ''}`}
            onClick={goInput}
          >
            New analysis
          </button>
          <button
            type="button"
            className={`nav-button ${view.name === 'history' ? 'nav-button--active' : ''}`}
            onClick={goHistory}
          >
            History
          </button>
        </nav>
      </header>

      <main>
        {view.name === 'input' && <InputPage onResult={(scan) => setView({ name: 'result', scan, origin: 'fresh' })} />}
        {view.name === 'result' && (
          <ResultPage
            scan={view.scan}
            origin={view.origin}
            onNewScan={goInput}
            onHistory={goHistory}
          />
        )}
        {view.name === 'history' && (
          <HistoryPage
            onView={(scan) => setView({ name: 'result', scan, origin: 'history' })}
            onNewScan={goInput}
          />
        )}
      </main>

      <footer className="app-footer">
        <p>
          Risk indicators are not proof of fraud. This tool gives heuristic
          guidance for students; always verify independently.
        </p>
      </footer>
    </div>
  )
}
