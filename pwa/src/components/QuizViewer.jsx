import React, { useEffect, useState } from 'react';
import { fetchQuiz } from '../api';

export default function QuizViewer({ filename, onBack }) {
  const [quizData, setQuizData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [currentQuestionIndex, setCurrentQuestionIndex] = useState(0);
  const [selectedOption, setSelectedOption] = useState(null);
  const [score, setScore] = useState(0);
  const [showResults, setShowResults] = useState(false);
  const [answered, setAnswered] = useState(false);

  useEffect(() => {
    const loadQuiz = async () => {
      try {
        const data = await fetchQuiz(filename);
        setQuizData(data);
      } catch (err) {
        setError(err.message);
      } finally {
        setLoading(false);
      }
    };
    loadQuiz();
  }, [filename]);

  if (loading) return <div className="fade-in subtitle">Loading quiz details...</div>;
  if (error) return <div className="fade-in error-banner">Error: {error}</div>;
  if (!quizData || !quizData.questions) return <div className="empty-state glass-panel">Invalid quiz data.</div>;

  const handleOptionClick = (option) => {
    if (answered) return;
    
    setSelectedOption(option);
    setAnswered(true);
    
    const currentQuestion = quizData.questions[currentQuestionIndex];
    if (option === currentQuestion.answer) {
      setScore(score + 1);
    }

    setTimeout(() => {
      if (currentQuestionIndex < quizData.questions.length - 1) {
        setCurrentQuestionIndex(currentQuestionIndex + 1);
        setSelectedOption(null);
        setAnswered(false);
      } else {
        setShowResults(true);
      }
    }, 1500);
  };

  const resetQuiz = () => {
    setCurrentQuestionIndex(0);
    setSelectedOption(null);
    setScore(0);
    setShowResults(false);
    setAnswered(false);
  };

  if (showResults) {
    return (
      <div className="quiz-viewer fade-in">
        <button className="back-btn mb-4" onClick={onBack}>← Back to Quizzes</button>
        <div className="quiz-results glass-panel">
          <h2>Quiz Completed!</h2>
          <div className="score-display">
            {score} / {quizData.questions.length}
          </div>
          <p className="subtitle">
            You scored {Math.round((score / quizData.questions.length) * 100)}%
          </p>
          <div className="quiz-results-actions">
            <button className="btn-primary" onClick={resetQuiz}>Retry Quiz</button>
            <button className="btn-secondary" onClick={onBack}>Choose Another</button>
          </div>
        </div>
      </div>
    );
  }

  const currentQuestion = quizData.questions[currentQuestionIndex];

  return (
    <div className="quiz-viewer fade-in">
      <button className="back-btn mb-4" onClick={onBack}>
        ← Back to Quizzes
      </button>

      <div className="quiz-header glass-panel">
        <h2>{quizData.subject || filename.replace('.json', '')}</h2>
        {quizData.date && <div className="quiz-meta">Date: {quizData.date}</div>}
        <div className="quiz-meta">
          Question {currentQuestionIndex + 1} of {quizData.questions.length}
        </div>
      </div>

      <div className="question-card glass-panel fade-in" key={currentQuestionIndex}>
        <div className="question-text">{currentQuestion.question}</div>
        
        <div className="options-grid">
          {currentQuestion.options.map((option, idx) => {
            let btnClass = "option-btn";
            if (answered) {
              if (option === currentQuestion.answer) {
                btnClass += " correct";
              } else if (option === selectedOption) {
                btnClass += " wrong";
              }
            } else if (option === selectedOption) {
              btnClass += " selected";
            }

            return (
              <button 
                key={idx} 
                className={btnClass}
                onClick={() => handleOptionClick(option)}
                disabled={answered}
              >
                <span>{option}</span>
                {answered && option === currentQuestion.answer && <span>✓</span>}
                {answered && option === selectedOption && option !== currentQuestion.answer && <span>✗</span>}
              </button>
            );
          })}
        </div>
      </div>
    </div>
  );
}
