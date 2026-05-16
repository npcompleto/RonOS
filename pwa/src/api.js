const API_BASE_URL = 'http://localhost:8001/api';

export const fetchQuizzes = async () => {
  const response = await fetch(`${API_BASE_URL}/quizzes`);
  if (!response.ok) {
    throw new Error('Failed to fetch quizzes');
  }
  return response.json();
};

export const fetchQuiz = async (filename) => {
  const response = await fetch(`${API_BASE_URL}/quizzes/${filename}`);
  if (!response.ok) {
    throw new Error('Failed to fetch quiz details');
  }
  return response.json();
};
