export type RiskBand = 'LOW' | 'MODERATE' | 'HIGH' | 'VERY_HIGH' | 'UNCERTAIN'

export type InputType = 'text' | 'url' | 'image'

export type EvidenceSource = 'text' | 'url' | 'ocr'

export interface EvidenceItem {
  id: string
  source: EvidenceSource
  reason: string
  snippet: string
  weight: number
}

export interface UncertaintyInfo {
  level: 'low' | 'medium' | 'high'
  reasons: string[]
}

export interface ModuleScores {
  text: number
  url: number
  /** null = not retained (image is deleted after OCR, confidence is not stored). */
  ocr_confidence: number | null
}

export interface ExtractedData {
  urls: string[]
  emails: string[]
  phones: string[]
  domains: string[]
}

export interface ScanResponse {
  id: string
  created_at: string
  input_types: InputType[]
  risk_score: number
  risk_band: RiskBand
  score_note: string
  category: string | null
  uncertainty: UncertaintyInfo
  modules: ModuleScores
  evidence: EvidenceItem[]
  extracted: ExtractedData
  recommendations: string[]
  disclaimer: string
  mode: 'rules' | 'ml' | 'demo'
  ocr_text: string | null
}

export interface ScanListItem {
  id: string
  created_at: string
  input_types: InputType[]
  risk_score: number
  risk_band: RiskBand
  category: string | null
}

export interface FeedbackResult {
  message: string
}
