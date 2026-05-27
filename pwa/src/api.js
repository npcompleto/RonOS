const API_BASE_URL = `http://${window.location.hostname}:8001/api`;

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

export const fetchPlaylists = async () => {
  const response = await fetch(`${API_BASE_URL}/playlists`);
  if (!response.ok) {
    throw new Error('Failed to fetch playlists');
  }
  return response.json();
};

export const createPlaylist = async (name) => {
  const response = await fetch(`${API_BASE_URL}/playlists`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ name }),
  });
  if (!response.ok) {
    throw new Error('Failed to create playlist');
  }
  return response.json();
};

export const deletePlaylist = async (name) => {
  const response = await fetch(`${API_BASE_URL}/playlists/${encodeURIComponent(name)}`, {
    method: 'DELETE',
  });
  if (!response.ok) {
    throw new Error('Failed to delete playlist');
  }
  return response.json();
};

export const fetchCacheSongs = async () => {
  const response = await fetch(`${API_BASE_URL}/cache_songs`);
  if (!response.ok) {
    throw new Error('Failed to fetch cache songs');
  }
  return response.json();
};

export const removeSongFromPlaylist = async (playlistName, songName) => {
  const response = await fetch(
    `${API_BASE_URL}/playlists/${encodeURIComponent(playlistName)}/songs/${encodeURIComponent(songName)}`,
    { method: 'DELETE' }
  );
  if (!response.ok) {
    throw new Error('Failed to remove song from playlist');
  }
  return response.json();
};

export const addSongToPlaylist = async (songName, playlistName) => {
  const response = await fetch(`${API_BASE_URL}/playlists/add_song`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ song_name: songName, playlist_name: playlistName }),
  });
  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || 'Failed to add song to playlist');
  }
  return response.json();
};

export const deleteCacheSong = async (songName) => {
  const response = await fetch(
    `${API_BASE_URL}/cache_songs/${encodeURIComponent(songName)}`,
    { method: 'DELETE' }
  );
  if (!response.ok) {
    throw new Error('Failed to delete song');
  }
  return response.json();
};

export const downloadCacheSong = async (url) => {
  const response = await fetch(`${API_BASE_URL}/cache_songs/download`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ url }),
  });
  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || 'Failed to download song');
  }
  return response.json();
};
