import axios from 'axios'
import type {
  EvaluationReport, GlobalStats, ScanListItem, ScanResult,
} from './types'

const BASE = '/api/v1'

const http = axios.create({ baseURL: BASE, timeout: 120_000 })

export const api = {
  health: () => http.get<{ status: string; clang: string }>('/health'),

  analyze: (payload: {
    source_code: string
    filename: string
    language: string
    opt_levels: string[]
    include_o3: boolean
  }) => http.post<ScanResult>('/analyze', payload),

  listScans: () => http.get<ScanListItem[]>('/scans'),

  getScan: (id: string) => http.get<ScanResult>(`/scans/${id}`),

  deleteScan: (id: string) => http.delete(`/scans/${id}`),

  exportJson: (id: string) =>
    window.open(`${BASE}/scans/${id}/export/json`, '_blank'),

  exportPdf: (id: string) =>
    window.open(`${BASE}/scans/${id}/export/pdf`, '_blank'),

  getStats: () => http.get<GlobalStats>('/stats'),

  runEvaluation: () => http.get<EvaluationReport>('/evaluation'),
}
