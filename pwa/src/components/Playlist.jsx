import React, { useEffect, useState } from 'react';
import { fetchPlaylists, createPlaylist, deletePlaylist, fetchCacheSongs, removeSongFromPlaylist, addSongToPlaylist, deleteCacheSong, downloadCacheSong } from '../api';
import { logger } from '../logger';

export default function Playlist({ onBack }) {
  const [playlists, setPlaylists] = useState([]);
  const [cacheSongs, setCacheSongs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [showCreateForm, setShowCreateForm] = useState(false);
  const [newPlaylistName, setNewPlaylistName] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [deleteConfirm, setDeleteConfirm] = useState(null);
  const [expandedPlaylist, setExpandedPlaylist] = useState(null);
  const [songToAddToPlaylist, setSongToAddToPlaylist] = useState(null);
  const [selectedPlaylistForSong, setSelectedPlaylistForSong] = useState('');
  const [downloadUrl, setDownloadUrl] = useState('');
  const [isDownloading, setIsDownloading] = useState(false);

  useEffect(() => {
    logger.info('Playlist component mounted, loading playlists and cache songs');
    loadPlaylists();
    loadCacheSongs();
  }, []);

  const loadPlaylists = async () => {
    try {
      setLoading(true);
      logger.debug('Fetching playlists list');
      const data = await fetchPlaylists();
      setPlaylists(data.playlists || []);
      logger.info(`Loaded ${data.playlists?.length || 0} playlists`);
    } catch (err) {
      logger.error(`Failed to load playlists: ${err.message}`);
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const loadCacheSongs = async () => {
    try {
      logger.debug('Fetching cache songs');
      const data = await fetchCacheSongs();
      setCacheSongs(data.songs || []);
      logger.info(`Loaded ${data.songs?.length || 0} cache songs`);
    } catch (err) {
      logger.error(`Failed to load cache songs: ${err.message}`);
    }
  };

  const handleCreatePlaylist = async (e) => {
    e.preventDefault();
    if (!newPlaylistName.trim()) return;

    try {
      setIsSubmitting(true);
      logger.info(`Creating new playlist: ${newPlaylistName}`);
      await createPlaylist(newPlaylistName);
      logger.info(`Playlist created successfully: ${newPlaylistName}`);
      setNewPlaylistName('');
      setShowCreateForm(false);
      await loadPlaylists();
    } catch (err) {
      logger.error(`Failed to create playlist: ${err.message}`);
      setError(err.message);
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleDeletePlaylist = async (playlistName) => {
    try {
      logger.info(`Deleting playlist: ${playlistName}`);
      await deletePlaylist(playlistName);
      logger.info(`Playlist deleted successfully: ${playlistName}`);
      setDeleteConfirm(null);
      await loadPlaylists();
    } catch (err) {
      logger.error(`Failed to delete playlist: ${err.message}`);
      setError(err.message);
    }
  };

  const handleRemoveSongFromPlaylist = async (playlistName, songName) => {
    try {
      logger.info(`Removing song from playlist: ${playlistName} - ${songName}`);
      await removeSongFromPlaylist(playlistName, songName);
      logger.info(`Song removed successfully`);
      await loadPlaylists();
    } catch (err) {
      logger.error(`Failed to remove song: ${err.message}`);
      setError(err.message);
    }
  };

  const handleAddSongToPlaylist = async () => {
    if (!selectedPlaylistForSong || !songToAddToPlaylist) return;

    try {
      logger.info(`Adding song to playlist: ${selectedPlaylistForSong} - ${songToAddToPlaylist}`);
      await addSongToPlaylist(songToAddToPlaylist, selectedPlaylistForSong);
      logger.info(`Song added successfully`);
      setSongToAddToPlaylist(null);
      setSelectedPlaylistForSong('');
      await loadPlaylists();
    } catch (err) {
      logger.error(`Failed to add song: ${err.message}`);
      setError(err.message);
    }
  };

  const handleDeleteCacheSong = async (songName) => {
    if (!window.confirm(`Are you sure you want to delete "${songName}"? This action cannot be undone.`)) {
      return;
    }

    try {
      logger.info(`Deleting song from cache: ${songName}`);
      await deleteCacheSong(songName);
      logger.info(`Song deleted successfully`);
      await loadCacheSongs();
    } catch (err) {
      logger.error(`Failed to delete song: ${err.message}`);
      setError(err.message);
    }
  };

  const handleDownloadUrl = async () => {
    if (!downloadUrl.trim()) {
      setError('Please enter a valid URL');
      return;
    }

    try {
      setError(null);
      setIsDownloading(true);
      logger.info(`Downloading song from: ${downloadUrl}`);
      await downloadCacheSong(downloadUrl.trim());
      logger.info('Download completed successfully');
      setDownloadUrl('');
      await loadCacheSongs();
    } catch (err) {
      logger.error(`Failed to download song: ${err.message}`);
      setError(err.message);
    } finally {
      setIsDownloading(false);
    }
  };

  if (loading) return (
    <div className="fade-in">
      <button className="back-btn mb-4" onClick={onBack}>← Back to Home</button>
      <div className="subtitle">Loading playlists...</div>
    </div>
  );

  return (
    <div className="fade-in">
      <button className="back-btn mb-4" onClick={onBack}>← Back to Home</button>
      <h2>My Playlists</h2>
      <p className="subtitle">
        Manage and create your custom playlists.
      </p>

      {error && (
        <div className="error-banner">
          Error: {error}
        </div>
      )}

      <button 
        className="btn-primary mb-4" 
        onClick={() => setShowCreateForm(!showCreateForm)}
      >
        {showCreateForm ? '✕ Cancel' : '+ Create New Playlist'}
      </button>

      {showCreateForm && (
        <div className="glass-panel mb-4" style={{ padding: '1.25rem' }}>
          <form onSubmit={handleCreatePlaylist}>
            <div className="create-playlist-form">
              <input
                className="form-input"
                type="text"
                placeholder="Enter playlist name..."
                value={newPlaylistName}
                onChange={(e) => setNewPlaylistName(e.target.value)}
                autoFocus
                disabled={isSubmitting}
              />
              <button 
                type="submit" 
                className="btn-primary"
                disabled={isSubmitting || !newPlaylistName.trim()}
              >
                {isSubmitting ? 'Creating...' : 'Create'}
              </button>
            </div>
          </form>
        </div>
      )}

      {playlists.length === 0 ? (
        <div className="glass-panel empty-state">
          <p>No playlists yet. Create one to get started!</p>
        </div>
      ) : (
        <div className="playlist-section">
          <h3 className="section-title">🎵 My Playlists</h3>
          <div className="playlist-list">
            {playlists.map((playlist) => (
              <div key={playlist.name} className="glass-panel playlist-card">
                <div
                  className="playlist-header-row"
                  onClick={() => setExpandedPlaylist(expandedPlaylist === playlist.name ? null : playlist.name)}
                >
                  <div className="playlist-info">
                    <span className="playlist-toggle-icon">
                      {expandedPlaylist === playlist.name ? '▼' : '▶'}
                    </span>
                    <div>
                      <h4>{playlist.name}</h4>
                      <p>
                        {playlist.songs?.length || 0} song{playlist.songs?.length !== 1 ? 's' : ''}
                      </p>
                    </div>
                  </div>
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      setDeleteConfirm(playlist.name);
                    }}
                    className="btn-danger"
                  >
                    Delete
                  </button>
                </div>

                {expandedPlaylist === playlist.name && (
                  <div className="playlist-expanded-content">
                    {playlist.songs && playlist.songs.length > 0 ? (
                      <ul className="song-list">
                        {playlist.songs.map((song, index) => (
                          <li key={index} className="song-item">
                            <div className="song-meta">
                              <span className="song-number">{index + 1}.</span>
                              <span className="song-name">{song}</span>
                            </div>
                            <div className="song-actions">
                              <button
                                className="icon-btn remove"
                                title="Remove from playlist"
                                onClick={() => handleRemoveSongFromPlaylist(playlist.name, song)}
                              >
                                ✕
                              </button>
                            </div>
                          </li>
                        ))}
                      </ul>
                    ) : (
                      <p className="subtitle" style={{ margin: 0 }}>No songs in this playlist yet.</p>
                    )}
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      <div className="playlist-section">
        <h3 className="section-title">📁 Cache Songs</h3>
        <p className="playlist-count">
          {cacheSongs.length} song{cacheSongs.length !== 1 ? 's' : ''} in cache
        </p>
        <div className="glass-panel mb-4" style={{ padding: '1.25rem' }}>
          <div className="download-form">
            <input
              className="form-input"
              type="text"
              placeholder="Enter URL to download..."
              value={downloadUrl}
              onChange={(e) => setDownloadUrl(e.target.value)}
            />
            <button
              type="button"
              className="btn-primary"
              onClick={handleDownloadUrl}
              disabled={isDownloading || !downloadUrl.trim()}
            >
              {isDownloading ? 'Downloading...' : 'Download URL'}
            </button>
          </div>
        </div>
        {cacheSongs.length === 0 ? (
          <div className="glass-panel empty-state">
            <p>No songs in cache yet.</p>
          </div>
        ) : (
          <div className="glass-panel" style={{ padding: '1rem' }}>
            <ul className="song-list">
              {cacheSongs.map((song, index) => (
                <li key={index} className="song-item">
                  <div className="song-meta">
                    <span className="song-number">{index + 1}.</span>
                    <span className="song-name">{song}</span>
                  </div>
                  <div className="song-actions">
                    <button
                      className="icon-btn add"
                      title="Add to playlist"
                      onClick={() => {
                        setSongToAddToPlaylist(song);
                        setSelectedPlaylistForSong('');
                      }}
                    >
                      ➕
                    </button>
                    <button
                      className="icon-btn delete"
                      title="Delete file"
                      onClick={() => handleDeleteCacheSong(song)}
                    >
                      🗑️
                    </button>
                  </div>
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>

      {songToAddToPlaylist && (
        <div className="modal-overlay">
          <div className="glass-panel modal-content">
            <h3>Add to Playlist</h3>
            <p className="subtitle">
              Song: <strong>{songToAddToPlaylist}</strong>
            </p>
            
            {playlists.length === 0 ? (
              <p className="subtitle">
                No playlists available. Create one first.
              </p>
            ) : (
              <select
                className="form-select mb-4"
                value={selectedPlaylistForSong}
                onChange={(e) => setSelectedPlaylistForSong(e.target.value)}
              >
                <option value="">Select a playlist...</option>
                {playlists.map((playlist) => (
                  <option key={playlist.name} value={playlist.name}>
                    {playlist.name}
                  </option>
                ))}
              </select>
            )}

            <div className="modal-buttons">
              <button
                onClick={() => {
                  setSongToAddToPlaylist(null);
                  setSelectedPlaylistForSong('');
                }}
                className="btn-secondary"
              >
                Cancel
              </button>
              <button
                onClick={handleAddSongToPlaylist}
                className="btn-primary"
                disabled={!selectedPlaylistForSong || playlists.length === 0}
              >
                Add
              </button>
            </div>
          </div>
        </div>
      )}

      {deleteConfirm && (
        <div className="modal-overlay">
          <div className="glass-panel modal-content">
            <h3>Delete Playlist?</h3>
            <p className="subtitle">
              Are you sure you want to delete "{deleteConfirm}"? This action cannot be undone.
            </p>
            <div className="modal-buttons">
              <button 
                className="btn-danger"
                onClick={() => handleDeletePlaylist(deleteConfirm)}
              >
                Delete
              </button>
              <button 
                className="btn-secondary"
                onClick={() => setDeleteConfirm(null)}
              >
                Cancel
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
