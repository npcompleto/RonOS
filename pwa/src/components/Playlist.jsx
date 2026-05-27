import React, { useEffect, useState } from 'react';
import { fetchPlaylists, createPlaylist, deletePlaylist, fetchCacheSongs, removeSongFromPlaylist, addSongToPlaylist, deleteCacheSong } from '../api';
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

  if (loading) return (
    <div className="fade-in">
      <button className="back-btn mb-4" onClick={onBack}>← Back to Home</button>
      <div>Loading playlists...</div>
    </div>
  );

  return (
    <div className="fade-in">
      <button className="back-btn mb-4" onClick={onBack}>← Back to Home</button>
      <h2>My Playlists</h2>
      <p style={{ color: 'var(--text-secondary)', marginBottom: '2rem' }}>
        Manage and create your custom playlists.
      </p>

      {error && (
        <div style={{ 
          color: 'var(--danger)', 
          backgroundColor: 'rgba(239, 68, 68, 0.1)',
          padding: '1rem',
          borderRadius: '0.5rem',
          marginBottom: '2rem'
        }}>
          Error: {error}
        </div>
      )}

      <button 
        className="btn-primary" 
        onClick={() => setShowCreateForm(!showCreateForm)}
        style={{ marginBottom: '2rem' }}
      >
        {showCreateForm ? '✕ Cancel' : '+ Create New Playlist'}
      </button>

      {showCreateForm && (
        <div className="glass-panel" style={{ padding: '1.5rem', marginBottom: '2rem' }}>
          <form onSubmit={handleCreatePlaylist}>
            <div style={{ display: 'flex', gap: '1rem', marginBottom: '1rem' }}>
              <input
                type="text"
                placeholder="Enter playlist name..."
                value={newPlaylistName}
                onChange={(e) => setNewPlaylistName(e.target.value)}
                style={{
                  flex: 1,
                  padding: '0.75rem',
                  borderRadius: '0.5rem',
                  border: '1px solid var(--border)',
                  backgroundColor: 'var(--bg-secondary)',
                  color: 'var(--text)',
                  fontFamily: 'inherit'
                }}
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
        <div className="glass-panel" style={{ padding: '2rem', textAlign: 'center', color: 'var(--text-secondary)' }}>
          <p>No playlists yet. Create one to get started!</p>
        </div>
      ) : (
        <div style={{ marginBottom: '2rem' }}>
          <h3 style={{ marginBottom: '1rem' }}>🎵 My Playlists</h3>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
            {playlists.map((playlist) => (
              <div key={playlist.name} className="glass-panel" style={{ padding: 0, overflow: 'hidden' }}>
                <div
                  onClick={() => setExpandedPlaylist(expandedPlaylist === playlist.name ? null : playlist.name)}
                  style={{
                    padding: '1rem 1.5rem',
                    cursor: 'pointer',
                    display: 'flex',
                    justifyContent: 'space-between',
                    alignItems: 'center',
                    transition: 'background-color 0.2s ease'
                  }}
                  onMouseEnter={(e) => e.currentTarget.style.backgroundColor = 'rgba(255, 255, 255, 0.05)'}
                  onMouseLeave={(e) => e.currentTarget.style.backgroundColor = 'transparent'}
                >
                  <div style={{ display: 'flex', alignItems: 'center', gap: '1rem', flex: 1 }}>
                    <span style={{ fontSize: '1.2rem' }}>
                      {expandedPlaylist === playlist.name ? '▼' : '▶'}
                    </span>
                    <div>
                      <h4 style={{ margin: '0 0 0.25rem 0' }}>{playlist.name}</h4>
                      <p style={{ margin: 0, color: 'var(--text-secondary)', fontSize: '0.85rem' }}>
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
                    style={{ padding: '0.5rem 1rem', fontSize: '0.9rem' }}
                  >
                    Delete
                  </button>
                </div>

                {expandedPlaylist === playlist.name && (
                  <div style={{ borderTop: '1px solid var(--border)', padding: '1.5rem' }}>
                    {playlist.songs && playlist.songs.length > 0 ? (
                      <ul style={{ listStyle: 'none', padding: 0, margin: 0 }}>
                        {playlist.songs.map((song, index) => (
                          <li key={index} style={{ 
                            padding: '0.75rem',
                            borderBottom: index < playlist.songs.length - 1 ? '1px solid var(--border)' : 'none',
                            color: 'var(--text)',
                            display: 'flex',
                            gap: '0.75rem',
                            alignItems: 'center',
                            justifyContent: 'space-between'
                          }}>
                            <div style={{ display: 'flex', gap: '0.75rem', flex: 1, alignItems: 'center' }}>
                              <span style={{ color: 'var(--text-secondary)', minWidth: '1.5rem' }}>{index + 1}.</span>
                              <span style={{ flex: 1, wordBreak: 'break-word' }}>{song}</span>
                            </div>
                            <button
                              onClick={() => handleRemoveSongFromPlaylist(playlist.name, song)}
                              style={{
                                padding: '0.4rem 0.75rem',
                                backgroundColor: 'rgba(239, 68, 68, 0.2)',
                                color: 'var(--danger)',
                                border: '1px solid rgba(239, 68, 68, 0.3)',
                                borderRadius: '0.35rem',
                                cursor: 'pointer',
                                fontSize: '0.8rem',
                                fontFamily: 'inherit',
                                whiteSpace: 'nowrap',
                                transition: 'all 0.2s ease'
                              }}
                              onMouseEnter={(e) => {
                                e.currentTarget.style.backgroundColor = 'rgba(239, 68, 68, 0.3)';
                                e.currentTarget.style.borderColor = 'rgba(239, 68, 68, 0.5)';
                              }}
                              onMouseLeave={(e) => {
                                e.currentTarget.style.backgroundColor = 'rgba(239, 68, 68, 0.2)';
                                e.currentTarget.style.borderColor = 'rgba(239, 68, 68, 0.3)';
                              }}
                            >
                              ✕ Remove
                            </button>
                          </li>
                        ))}
                      </ul>
                    ) : (
                      <p style={{ color: 'var(--text-secondary)', margin: 0 }}>No songs in this playlist yet.</p>
                    )}
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      <div style={{ marginTop: '3rem' }}>
        <h3 style={{ marginBottom: '1rem' }}>📁 Cache Songs</h3>
        <p style={{ color: 'var(--text-secondary)', marginBottom: '1.5rem' }}>
          {cacheSongs.length} song{cacheSongs.length !== 1 ? 's' : ''} in cache
        </p>
        {cacheSongs.length === 0 ? (
          <div className="glass-panel" style={{ padding: '2rem', textAlign: 'center', color: 'var(--text-secondary)' }}>
            <p>No songs in cache yet.</p>
          </div>
        ) : (
          <div className="glass-panel" style={{ padding: '1.5rem' }}>
            <ul style={{ listStyle: 'none', padding: 0, margin: 0 }}>
              {cacheSongs.map((song, index) => (
                <li key={index} style={{ 
                  padding: '0.75rem',
                  borderBottom: index < cacheSongs.length - 1 ? '1px solid var(--border)' : 'none',
                  color: 'var(--text)',
                  display: 'flex',
                  gap: '0.75rem',
                  alignItems: 'center',
                  justifyContent: 'space-between'
                }}>
                  <div style={{ display: 'flex', gap: '0.75rem', flex: 1, alignItems: 'center' }}>
                    <span style={{ color: 'var(--text-secondary)', minWidth: '1.5rem' }}>{index + 1}.</span>
                    <span style={{ flex: 1, wordBreak: 'break-word' }}>{song}</span>
                  </div>
                  <div style={{ display: 'flex', gap: '0.5rem' }}>
                    <button
                      onClick={() => {
                        setSongToAddToPlaylist(song);
                        setSelectedPlaylistForSong('');
                      }}
                      style={{
                        padding: '0.4rem 0.75rem',
                        backgroundColor: 'rgba(59, 130, 246, 0.2)',
                        color: 'var(--text)',
                        border: '1px solid rgba(59, 130, 246, 0.3)',
                        borderRadius: '0.35rem',
                        cursor: 'pointer',
                        fontSize: '0.8rem',
                        fontFamily: 'inherit',
                        whiteSpace: 'nowrap',
                        transition: 'all 0.2s ease'
                      }}
                      onMouseEnter={(e) => {
                        e.currentTarget.style.backgroundColor = 'rgba(59, 130, 246, 0.3)';
                        e.currentTarget.style.borderColor = 'rgba(59, 130, 246, 0.5)';
                      }}
                      onMouseLeave={(e) => {
                        e.currentTarget.style.backgroundColor = 'rgba(59, 130, 246, 0.2)';
                        e.currentTarget.style.borderColor = 'rgba(59, 130, 246, 0.3)';
                      }}
                    >
                      + Add to Playlist
                    </button>
                    <button
                      onClick={() => handleDeleteCacheSong(song)}
                      style={{
                        padding: '0.4rem 0.75rem',
                        backgroundColor: 'rgba(239, 68, 68, 0.2)',
                        color: 'var(--danger)',
                        border: '1px solid rgba(239, 68, 68, 0.3)',
                        borderRadius: '0.35rem',
                        cursor: 'pointer',
                        fontSize: '0.8rem',
                        fontFamily: 'inherit',
                        whiteSpace: 'nowrap',
                        transition: 'all 0.2s ease'
                      }}
                      onMouseEnter={(e) => {
                        e.currentTarget.style.backgroundColor = 'rgba(239, 68, 68, 0.3)';
                        e.currentTarget.style.borderColor = 'rgba(239, 68, 68, 0.5)';
                      }}
                      onMouseLeave={(e) => {
                        e.currentTarget.style.backgroundColor = 'rgba(239, 68, 68, 0.2)';
                        e.currentTarget.style.borderColor = 'rgba(239, 68, 68, 0.3)';
                      }}
                    >
                      🗑️ Delete
                    </button>
                  </div>
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>

      {songToAddToPlaylist && (
        <div style={{
          position: 'fixed',
          top: 0,
          left: 0,
          right: 0,
          bottom: 0,
          backgroundColor: 'rgba(0, 0, 0, 0.5)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          zIndex: 1000
        }}>
          <div className="glass-panel" style={{ padding: '2rem', maxWidth: '400px' }}>
            <h3>Add to Playlist</h3>
            <p style={{ color: 'var(--text-secondary)', marginBottom: '1.5rem' }}>
              Song: <strong>{songToAddToPlaylist}</strong>
            </p>
            
            {playlists.length === 0 ? (
              <p style={{ color: 'var(--text-secondary)', marginBottom: '1.5rem' }}>
                No playlists available. Create one first.
              </p>
            ) : (
              <>
                <select
                  value={selectedPlaylistForSong}
                  onChange={(e) => setSelectedPlaylistForSong(e.target.value)}
                  style={{
                    width: '100%',
                    padding: '0.75rem',
                    marginBottom: '1.5rem',
                    borderRadius: '0.5rem',
                    border: '1px solid var(--border)',
                    backgroundColor: 'var(--bg-secondary)',
                    color: 'var(--text)',
                    fontFamily: 'inherit',
                    fontSize: '1rem',
                    cursor: 'pointer'
                  }}
                >
                  <option value="">Select a playlist...</option>
                  {playlists.map((playlist) => (
                    <option key={playlist.name} value={playlist.name}>
                      {playlist.name}
                    </option>
                  ))}
                </select>
              </>
            )}

            <div style={{ display: 'flex', gap: '1rem' }}>
              <button
                onClick={() => {
                  setSongToAddToPlaylist(null);
                  setSelectedPlaylistForSong('');
                }}
                className="btn-secondary"
                style={{ flex: 1 }}
              >
                Cancel
              </button>
              <button
                onClick={handleAddSongToPlaylist}
                className="btn-primary"
                style={{ flex: 1 }}
                disabled={!selectedPlaylistForSong || playlists.length === 0}
              >
                Add
              </button>
            </div>
          </div>
        </div>
      )}

      {deleteConfirm && (
        <div style={{
          position: 'fixed',
          top: 0,
          left: 0,
          right: 0,
          bottom: 0,
          backgroundColor: 'rgba(0, 0, 0, 0.5)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          zIndex: 1000
        }}>
          <div className="glass-panel" style={{ padding: '2rem', maxWidth: '400px' }}>
            <h3>Delete Playlist?</h3>
            <p style={{ color: 'var(--text-secondary)', marginBottom: '1.5rem' }}>
              Are you sure you want to delete "{deleteConfirm}"? This action cannot be undone.
            </p>
            <div style={{ display: 'flex', gap: '1rem' }}>
              <button 
                className="btn-danger"
                onClick={() => handleDeletePlaylist(deleteConfirm)}
                style={{ flex: 1 }}
              >
                Delete
              </button>
              <button 
                className="back-btn"
                onClick={() => setDeleteConfirm(null)}
                style={{ flex: 1 }}
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
