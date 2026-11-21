import React, { useState, useEffect, useRef } from 'react';
import { FileIcon, DownloadIcon, TrashIcon, RefreshIcon, SearchIcon, PlusIcon } from '../icons/Icons';
import {
  fetchArtifacts,
  uploadArtifactToGarage,
  deleteArtifact,
  getArtifactDownloadUrl,
  getArtifactContentUrl,
  type ApiArtifactItem,
} from '../../services/api';

type Origin = 'all' | 'user_upload' | 'agent_generated';

const FILTERS: { id: Origin; label: string }[] = [
  { id: 'all', label: 'All' },
  { id: 'user_upload', label: 'Uploaded' },
  { id: 'agent_generated', label: 'Generated' },
];

const formatSize = (bytes: number) => {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
};

const formatDate = (iso: string) => {
  try {
    return new Date(iso).toLocaleString([], { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' });
  } catch {
    return iso;
  }
};

export const ArtifactsView: React.FC = () => {
  const [artifacts, setArtifacts] = useState<ApiArtifactItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [search, setSearch] = useState('');
  const [filterOrigin, setFilterOrigin] = useState<Origin>('all');
  const [isUploading, setIsUploading] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const loadData = async () => {
    setLoading(true);
    try {
      setArtifacts(await fetchArtifacts());
    } catch (e) {
      console.error('Failed to load artifacts:', e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  const handleFileChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setIsUploading(true);
    setUploadError(null);
    try {
      await uploadArtifactToGarage(file);
      await loadData();
    } catch (err: any) {
      setUploadError(err.message || 'Upload failed');
    } finally {
      setIsUploading(false);
      if (fileInputRef.current) fileInputRef.current.value = '';
    }
  };

  const handleDelete = async (id: string, name: string) => {
    if (!window.confirm(`Delete '${name}'?`)) return;
    try {
      await deleteArtifact(id);
      setArtifacts((prev) => prev.filter((a) => a.id !== id));
    } catch (err: any) {
      alert(`Delete error: ${err.message}`);
    }
  };

  const q = search.toLowerCase();
  const filtered = artifacts.filter((item) => {
    const matchesSearch = item.name.toLowerCase().includes(q) || (item.kind && item.kind.toLowerCase().includes(q));
    return matchesSearch && (filterOrigin === 'all' || item.origin === filterOrigin);
  });

  return (
    <div className="art-root">
      <input type="file" ref={fileInputRef} onChange={handleFileChange} style={{ display: 'none' }} />

      <div className="art-header">
        <div>
          <h1 className="art-title">Artifacts</h1>
          <p className="art-sub">Files you uploaded and deliverables your agents produced.</p>
        </div>
        <div className="art-actions">
          <button type="button" className="art-btn" onClick={loadData} disabled={loading}>
            <RefreshIcon size={14} /> Refresh
          </button>
          <button
            type="button"
            className="art-btn art-btn-primary"
            onClick={() => fileInputRef.current?.click()}
            disabled={isUploading}
          >
            <PlusIcon size={14} /> {isUploading ? 'Uploading…' : 'Upload'}
          </button>
        </div>
      </div>

      {uploadError && <div className="art-error">{uploadError}</div>}

      <div className="art-toolbar">
        <label className="art-search">
          <SearchIcon size={15} />
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search by name or kind"
          />
        </label>
        <div className="art-filters">
          {FILTERS.map((f) => (
            <button
              key={f.id}
              type="button"
              className={`art-filter ${filterOrigin === f.id ? 'is-active' : ''}`}
              onClick={() => setFilterOrigin(f.id)}
            >
              {f.label}
            </button>
          ))}
        </div>
      </div>

      {loading ? (
        <div className="art-empty">Loading…</div>
      ) : filtered.length === 0 ? (
        <div className="art-empty">
          <FileIcon size={32} />
          <p>No artifacts yet. Upload a file or ask an agent to produce one.</p>
        </div>
      ) : (
        <ul className="art-list">
          {filtered.map((item) => (
            <li key={item.id} className="art-row">
              <span className="art-row-icon">
                <FileIcon size={18} />
              </span>
              <div className="art-row-main">
                <span className="art-row-name" title={item.name}>
                  {item.name}
                </span>
                <span className="art-row-meta">
                  {item.origin === 'user_upload' ? 'Uploaded' : 'Generated'} · {formatSize(item.size_bytes)} ·{' '}
                  {formatDate(item.created_at)}
                </span>
              </div>
              <div className="art-row-actions">
                <a className="art-link" href={getArtifactContentUrl(item.id)} target="_blank" rel="noreferrer">
                  View
                </a>
                <a className="art-link" href={getArtifactDownloadUrl(item.id)} download={item.name} title="Download">
                  <DownloadIcon size={14} />
                </a>
                <button
                  type="button"
                  className="art-link art-link-danger"
                  onClick={() => handleDelete(item.id, item.name)}
                  title="Delete"
                >
                  <TrashIcon size={14} />
                </button>
              </div>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
};
