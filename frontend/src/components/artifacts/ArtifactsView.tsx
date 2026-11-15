import React, { useState, useEffect, useRef } from 'react';
import {
  FileIcon,
  DownloadIcon,
  TrashIcon,
  RefreshIcon,
  SearchIcon,
  PlusIcon
} from '../icons/Icons';

import { Badge, Button } from '../common';
import {
  fetchArtifacts,
  uploadArtifactToGarage,
  deleteArtifact,
  getArtifactDownloadUrl,
  getArtifactContentUrl,
  type ApiArtifactItem
} from '../../services/api';

export const ArtifactsView: React.FC = () => {
  const [artifacts, setArtifacts] = useState<ApiArtifactItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [search, setSearch] = useState('');
  const [filterOrigin, setFilterOrigin] = useState<'all' | 'user_upload' | 'agent_generated'>('all');
  const [isUploading, setIsUploading] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);

  const fileInputRef = useRef<HTMLInputElement>(null);

  const loadData = async () => {
    setLoading(true);
    try {
      const data = await fetchArtifacts();
      setArtifacts(data);
    } catch (e) {
      console.error('Failed to load artifacts:', e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  const handleUploadClick = () => {
    if (fileInputRef.current) {
      fileInputRef.current.click();
    }
  };

  const handleFileChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    setIsUploading(true);
    setUploadError(null);
    try {
      await uploadArtifactToGarage(file);
      await loadData();
    } catch (err: any) {
      setUploadError(err.message || 'Failed to upload to Garage S3');
    } finally {
      setIsUploading(false);
      if (fileInputRef.current) fileInputRef.current.value = '';
    }
  };

  const handleDelete = async (id: string, name: string) => {
    if (!window.confirm(`Are you sure you want to delete artifact '${name}' from Garage S3?`)) {
      return;
    }
    try {
      await deleteArtifact(id);
      setArtifacts((prev) => prev.filter((a) => a.id !== id));
    } catch (err: any) {
      alert(`Delete error: ${err.message}`);
    }
  };

  const formatSize = (bytes: number) => {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  };

  const formatDate = (isoStr: string) => {
    try {
      return new Date(isoStr).toLocaleString([], {
        month: 'short',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit'
      });
    } catch {
      return isoStr;
    }
  };

  const filtered = artifacts.filter((item) => {
    const matchesSearch = item.name.toLowerCase().includes(search.toLowerCase()) ||
      (item.kind && item.kind.toLowerCase().includes(search.toLowerCase()));
    const matchesOrigin = filterOrigin === 'all' || item.origin === filterOrigin;
    return matchesSearch && matchesOrigin;
  });

  const totalBytes = artifacts.reduce((acc, cur) => acc + (cur.size_bytes || 0), 0);
  const userUploadsCount = artifacts.filter((a) => a.origin === 'user_upload').length;
  const agentGeneratedCount = artifacts.filter((a) => a.origin === 'agent_generated').length;

  return (
    <div style={{ flex: 1, overflowY: 'auto', padding: '28px 36px', color: '#f3f4f6' }}>
      {/* Hidden file input */}
      <input
        type="file"
        ref={fileInputRef}
        onChange={handleFileChange}
        style={{ display: 'none' }}
      />

      {/* Header Banner */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '24px', flexWrap: 'wrap', gap: '16px' }}>
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <h1 style={{ fontSize: '24px', fontWeight: 600, margin: 0, letterSpacing: '-0.02em' }}>
              Garage Object Storage Artifacts
            </h1>
            <Badge variant="primary" size="sm">Garage S3 Active</Badge>
          </div>
          <p style={{ margin: '6px 0 0 0', color: '#9ca3af', fontSize: '14px' }}>
            All user uploads and agent-generated deliverables stored reliably in Garage S3 (no local disk files).
          </p>
        </div>

        <div style={{ display: 'flex', gap: '10px' }}>
          <Button
            variant="secondary"
            size="md"
            icon={<RefreshIcon size={15} />}
            onClick={loadData}
            disabled={loading}
          >
            Refresh
          </Button>
          <Button
            variant="primary"
            size="md"
            icon={<PlusIcon size={15} />}
            onClick={handleUploadClick}
            disabled={isUploading}
          >
            {isUploading ? 'Uploading...' : 'Upload to Garage'}
          </Button>
        </div>
      </div>

      {uploadError && (
        <div style={{ background: 'rgba(239, 68, 68, 0.15)', border: '1px solid rgba(239, 68, 68, 0.3)', color: '#fca5a5', padding: '10px 16px', borderRadius: '8px', marginBottom: '20px', fontSize: '13px' }}>
          {uploadError}
        </div>
      )}

      {/* Metrics Row */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '16px', marginBottom: '28px' }}>
        <div style={{ background: '#111827', border: '1px solid #1f2937', borderRadius: '12px', padding: '16px 20px' }}>
          <div style={{ color: '#9ca3af', fontSize: '13px', marginBottom: '6px' }}>Total Artifacts</div>
          <div style={{ fontSize: '26px', fontWeight: 700, color: '#f9fafb' }}>{artifacts.length}</div>
        </div>
        <div style={{ background: '#111827', border: '1px solid #1f2937', borderRadius: '12px', padding: '16px 20px' }}>
          <div style={{ color: '#9ca3af', fontSize: '13px', marginBottom: '6px' }}>User Uploads</div>
          <div style={{ fontSize: '26px', fontWeight: 700, color: '#60a5fa' }}>{userUploadsCount}</div>
        </div>
        <div style={{ background: '#111827', border: '1px solid #1f2937', borderRadius: '12px', padding: '16px 20px' }}>
          <div style={{ color: '#9ca3af', fontSize: '13px', marginBottom: '6px' }}>Agent Deliverables</div>
          <div style={{ fontSize: '26px', fontWeight: 700, color: '#c084fc' }}>{agentGeneratedCount}</div>
        </div>
        <div style={{ background: '#111827', border: '1px solid #1f2937', borderRadius: '12px', padding: '16px 20px' }}>
          <div style={{ color: '#9ca3af', fontSize: '13px', marginBottom: '6px' }}>Garage Storage Used</div>
          <div style={{ fontSize: '26px', fontWeight: 700, color: '#34d399' }}>{formatSize(totalBytes)}</div>
        </div>
      </div>

      {/* Filter and Search Bar */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '18px', flexWrap: 'wrap', gap: '12px' }}>
        <div style={{ display: 'flex', alignItems: 'center', background: '#111827', border: '1px solid #1f2937', borderRadius: '8px', padding: '6px 12px', width: '320px' }}>
          <SearchIcon size={15} style={{ color: '#6b7280', marginRight: '8px' }} />
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search artifacts by name or kind..."
            style={{ background: 'transparent', border: 'none', color: '#f3f4f6', fontSize: '13px', width: '100%', outline: 'none' }}
          />
        </div>

        <div style={{ display: 'flex', gap: '8px' }}>
          <button
            type="button"
            onClick={() => setFilterOrigin('all')}
            style={{
              padding: '6px 14px',
              borderRadius: '6px',
              fontSize: '13px',
              cursor: 'pointer',
              border: 'none',
              background: filterOrigin === 'all' ? '#2563eb' : '#1f2937',
              color: filterOrigin === 'all' ? '#fff' : '#9ca3af',
            }}
          >
            All ({artifacts.length})
          </button>
          <button
            type="button"
            onClick={() => setFilterOrigin('user_upload')}
            style={{
              padding: '6px 14px',
              borderRadius: '6px',
              fontSize: '13px',
              cursor: 'pointer',
              border: 'none',
              background: filterOrigin === 'user_upload' ? '#2563eb' : '#1f2937',
              color: filterOrigin === 'user_upload' ? '#fff' : '#9ca3af',
            }}
          >
            User Uploaded ({userUploadsCount})
          </button>
          <button
            type="button"
            onClick={() => setFilterOrigin('agent_generated')}
            style={{
              padding: '6px 14px',
              borderRadius: '6px',
              fontSize: '13px',
              cursor: 'pointer',
              border: 'none',
              background: filterOrigin === 'agent_generated' ? '#2563eb' : '#1f2937',
              color: filterOrigin === 'agent_generated' ? '#fff' : '#9ca3af',
            }}
          >
            Agent Generated ({agentGeneratedCount})
          </button>
        </div>
      </div>

      {/* Artifacts List Table */}
      {loading ? (
        <div style={{ padding: '60px 0', textAlign: 'center', color: '#9ca3af' }}>
          Loading artifacts from Garage S3...
        </div>
      ) : filtered.length === 0 ? (
        <div style={{ padding: '60px 0', textAlign: 'center', background: '#111827', border: '1px dashed #374151', borderRadius: '12px' }}>
          <FileIcon size={38} style={{ color: '#4b5563', marginBottom: '12px' }} />
          <div style={{ fontSize: '16px', fontWeight: 500, color: '#e5e7eb', marginBottom: '6px' }}>No artifacts found</div>
          <p style={{ color: '#9ca3af', fontSize: '13px', margin: '0 0 16px 0' }}>
            Upload a file using the button above or ask agents to generate deliverables (resumes, scripts, reports).
          </p>
          <Button variant="primary" size="sm" onClick={handleUploadClick}>
            Upload your first artifact
          </Button>
        </div>
      ) : (
        <div style={{ background: '#111827', border: '1px solid #1f2937', borderRadius: '12px', overflow: 'hidden' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left', fontSize: '13px' }}>
            <thead>
              <tr style={{ borderBottom: '1px solid #1f2937', background: '#0f172a', color: '#9ca3af' }}>
                <th style={{ padding: '12px 18px', fontWeight: 500 }}>Name</th>
                <th style={{ padding: '12px 18px', fontWeight: 500 }}>Origin</th>
                <th style={{ padding: '12px 18px', fontWeight: 500 }}>Kind</th>
                <th style={{ padding: '12px 18px', fontWeight: 500 }}>Size</th>
                <th style={{ padding: '12px 18px', fontWeight: 500 }}>Created</th>
                <th style={{ padding: '12px 18px', fontWeight: 500 }}>Garage S3 Storage URI</th>
                <th style={{ padding: '12px 18px', fontWeight: 500, textAlign: 'right' }}>Actions</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((item) => {
                const isUserUpload = item.origin === 'user_upload';
                return (
                  <tr key={item.id} style={{ borderBottom: '1px solid #1f2937', transition: 'background 0.15s' }}>
                    <td style={{ padding: '14px 18px' }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                        <div style={{ color: isUserUpload ? '#60a5fa' : '#c084fc', display: 'flex' }}>
                          <FileIcon size={18} />
                        </div>
                        <div>
                          <div style={{ fontWeight: 600, color: '#f3f4f6' }}>{item.name}</div>
                          <div style={{ fontSize: '11px', color: '#6b7280' }}>{item.mime_type}</div>
                        </div>
                      </div>
                    </td>
                    <td style={{ padding: '14px 18px' }}>
                      <span
                        style={{
                          padding: '3px 8px',
                          borderRadius: '12px',
                          fontSize: '11px',
                          fontWeight: 500,
                          background: isUserUpload ? 'rgba(59, 130, 246, 0.15)' : 'rgba(168, 85, 247, 0.15)',
                          color: isUserUpload ? '#93c5fd' : '#d8b4fe',
                          border: isUserUpload ? '1px solid rgba(59, 130, 246, 0.3)' : '1px solid rgba(168, 85, 247, 0.3)',
                        }}
                      >
                        {isUserUpload ? 'User Upload' : 'Agent Generated'}
                      </span>
                    </td>
                    <td style={{ padding: '14px 18px' }}>
                      <span style={{ textTransform: 'uppercase', fontSize: '11px', fontWeight: 600, color: '#9ca3af' }}>
                        {item.kind}
                      </span>
                    </td>
                    <td style={{ padding: '14px 18px', color: '#d1d5db' }}>
                      {formatSize(item.size_bytes)}
                    </td>
                    <td style={{ padding: '14px 18px', color: '#9ca3af' }}>
                      {formatDate(item.created_at)}
                    </td>
                    <td style={{ padding: '14px 18px' }}>
                      <code style={{ fontSize: '11px', color: '#34d399', background: 'rgba(16, 185, 129, 0.08)', padding: '2px 6px', borderRadius: '4px' }}>
                        {item.storage_uri}
                      </code>
                    </td>
                    <td style={{ padding: '14px 18px', textAlign: 'right' }}>
                      <div style={{ display: 'flex', gap: '8px', justifyContent: 'flex-end' }}>
                        <a
                          href={getArtifactContentUrl(item.id)}
                          target="_blank"
                          rel="noreferrer"
                          style={{
                            padding: '5px 10px',
                            borderRadius: '6px',
                            background: '#1f2937',
                            color: '#93c5fd',
                            fontSize: '12px',
                            textDecoration: 'none',
                            display: 'inline-flex',
                            alignItems: 'center',
                          }}
                        >
                          View
                        </a>
                        <a
                          href={getArtifactDownloadUrl(item.id)}
                          download={item.name}
                          style={{
                            padding: '5px 10px',
                            borderRadius: '6px',
                            background: 'rgba(37, 99, 235, 0.2)',
                            color: '#60a5fa',
                            fontSize: '12px',
                            textDecoration: 'none',
                            display: 'inline-flex',
                            alignItems: 'center',
                            gap: '4px',
                          }}
                        >
                          <DownloadIcon size={13} />
                          Download
                        </a>
                        <button
                          type="button"
                          onClick={() => handleDelete(item.id, item.name)}
                          style={{
                            padding: '5px 8px',
                            borderRadius: '6px',
                            background: 'rgba(239, 68, 68, 0.15)',
                            color: '#f87171',
                            border: 'none',
                            cursor: 'pointer',
                            display: 'inline-flex',
                            alignItems: 'center',
                          }}
                          title="Delete from Garage S3"
                        >
                          <TrashIcon size={14} />
                        </button>
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
};
