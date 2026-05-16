import React, { useState } from 'react';
import './App.css';
import QuizList from './components/QuizList';
import QuizViewer from './components/QuizViewer';

function App() {
  const [selectedQuiz, setSelectedQuiz] = useState(null);

  return (
    <div className="app-container">
      <header className="header">
        <h1>Ron Quiz Hub</h1>
      </header>
      
      <main>
        {selectedQuiz ? (
          <QuizViewer 
            filename={selectedQuiz} 
            onBack={() => setSelectedQuiz(null)} 
          />
        ) : (
          <QuizList onSelectQuiz={setSelectedQuiz} />
        )}
      </main>
    </div>
  );
}

export default App;
