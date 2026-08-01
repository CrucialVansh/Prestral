import { Navigate, Route, Routes } from 'react-router-dom'
import Deck from './routes/Deck'
import Landing from './routes/Landing'
import Processing from './routes/Processing'

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<Landing />} />
      {/* Declared before the :slideIndex route so "processing" is never parsed
          as a slide number. */}
      <Route path="/deck/:deckId/processing" element={<Processing />} />
      <Route path="/deck/:deckId/:slideIndex" element={<Deck />} />
      <Route path="/present/:deckId/:slideIndex" element={<Deck mode="presenter" />} />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}
