import React, { useState } from 'react';
import './App.css';
import Home from './components/Home';
import QuizList from './components/QuizList';
import QuizViewer from './components/QuizViewer';
import Playlist from './components/Playlist';
import { logger } from './logger';

function App() {
  const [currentPage, setCurrentPage] = useState('home');
  const [selectedQuiz, setSelectedQuiz] = useState(null);

  const handleNavigate = (page) => {
    logger.info(`Navigating to ${page}`);
    setCurrentPage(page);
    setSelectedQuiz(null);
  };

  const handleBackToHome = () => {
    logger.info('Navigating back to home');
    setCurrentPage('home');
    setSelectedQuiz(null);
  };

  return (
    <div className="app-container">
      <header className="header">
        <h1>Ron Hub</h1>
        {currentPage !== 'home' && (
          <button 
            className="home-btn"
            onClick={handleBackToHome}
            style={{
              background: 'none',
              border: 'none',
              color: 'var(--text)',
              cursor: 'pointer',
              fontSize: '1.2rem',
              padding: '0.5rem 1rem'
            }}
          >
            🏠 Home
          </button>
        )}
      </header>
      
      <main>
        {currentPage === 'home' && <Home onNavigate={handleNavigate} />}
        
        {currentPage === 'quiz' && (
          selectedQuiz ? (
            <QuizViewer 
              filename={selectedQuiz} 
              onBack={() => setSelectedQuiz(null)} 
            />
          ) : (
            <QuizList onSelectQuiz={setSelectedQuiz} />
          )
        )}

        {currentPage === 'playlist' && <Playlist onBack={handleBackToHome} />}
      </main>
    </div>
  );
}

export default App;
