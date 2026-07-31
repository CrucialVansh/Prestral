#!/bin/bash
# Bash script to start both backend and frontend
# Run this from the Prestral directory using Git Bash or WSL

echo "Setting up environment..."

# Create frontend .env.local with real backend settings
cat > Frontend/.env.local << 'EOF'
VITE_USE_MOCK=false
VITE_API_TARGET=http://localhost:8000
EOF

echo "Starting backend server on port 8000..."
cd Backend
.venv/Scripts/activate
uvicorn app.main:app --reload --port 8000 &
BACKEND_PID=$!

cd ..

echo "Starting frontend server on port 5173..."
cd Frontend
npm run dev &
FRONTEND_PID=$!

cd ..

echo ""
echo "Both servers are now running:"
echo "  Backend: http://localhost:8000 (PID: $BACKEND_PID)"
echo "  Frontend: http://localhost:5173 (PID: $FRONTEND_PID)"
echo ""
echo "Press Ctrl+C to stop both servers"
echo ""

# Wait for both processes
wait $BACKEND_PID $FRONTEND_PID