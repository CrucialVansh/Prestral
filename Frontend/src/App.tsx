import { Navigate, Route, Routes } from 'react-router-dom'
import Deck from './routes/Deck'
import Processing from './routes/Processing'
import Upload from './routes/Upload'

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<Upload />} />
      {/* Declared before the :slideIndex route so "processing" is never parsed
          as a slide number. */}
      <Route path="/deck/:deckId/processing" element={<Processing />} />
      <Route path="/deck/:deckId/:slideIndex" element={<Deck />} />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}
