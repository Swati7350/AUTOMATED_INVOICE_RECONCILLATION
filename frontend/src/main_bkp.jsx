import React, { useRef, useState } from 'react'
import { createRoot } from 'react-dom/client'
import { Activity, ArrowDownToLine, ArrowRight, BadgeCheck, Bot, Check, CheckCircle2, ChevronDown, CircleAlert, CloudUpload, FileCheck2, FileText, Fingerprint, Gauge, Info, KeyRound, LoaderCircle, LockKeyhole, RefreshCw, ShieldCheck, Sparkles, X, Zap } from 'lucide-react'
import './styles.css'

const API_BASE = (import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000').replace(/\/$/, '')
const formatSize = bytes => bytes < 1024 * 1024 ? `${Math.max(1, Math.round(bytes / 1024))} KB` : `${(bytes / 1024 / 1024).toFixed(1)} MB`

function ParasAILogo() {
  return <div className="brand-lockup"><div className="brand-mark"><span/><span/><span/></div><div className="brand-copy"><strong>PARAS AI</strong><span>INNOVATIONS</span></div></div>
}
function StatusPill({ children, tone = 'neutral' }) { return <span className={`pill pill-${tone}`}><span className="pill-dot"/>{children}</span> }
function UploadCard({ title, subtitle, kind, file, setFile, disabled }) {
  const inputRef = useRef(null)
  const [dragging, setDragging] = useState(false)
  const onFile = candidate => { if (!candidate) return; if (candidate.type !== 'application/pdf' && !candidate.name.toLowerCase().endsWith('.pdf')) { alert('Please select a PDF file.'); return } setFile(candidate) }
  return <section className="upload-card">
    <div className="upload-card-top"><div className={`file-icon ${kind}`}><FileText size={19}/></div><div><h3>{title}</h3><p>{subtitle}</p></div><span className="required">PDF</span></div>
    <input ref={inputRef} type="file" accept="application/pdf,.pdf" hidden onChange={e => onFile(e.target.files?.[0])}/>
    <div className={`dropzone ${dragging ? 'dragging' : ''} ${file ? 'has-file' : ''}`} role="button" tabIndex={0} onClick={() => !disabled && inputRef.current?.click()} onKeyDown={e => e.key === 'Enter' && inputRef.current?.click()} onDragOver={e => {e.preventDefault();setDragging(true)}} onDragLeave={() => setDragging(false)} onDrop={e => {e.preventDefault();setDragging(false);onFile(e.dataTransfer.files?.[0])}}>
      {file ? <><div className="file-mini"><FileCheck2 size={20}/></div><div className="file-meta"><strong>{file.name}</strong><span>{formatSize(file.size)} · PDF document</span><div className="upload-track"><span/></div><small><CheckCircle2 size={12}/> Ready to process</small></div><button className="icon-button remove-file" title="Remove file" onClick={e => {e.stopPropagation();setFile(null);if(inputRef.current)inputRef.current.value=''}}><X size={16}/></button></> : <><div className="upload-symbol"><CloudUpload size={22}/></div><div><strong>Drop your PDF here, or <span>browse files</span></strong><p>PDF only · Select a file up to 20 MB</p></div></>}
    </div>
    <div className="upload-foot"><span><LockKeyhole size={13}/> Processed securely in memory</span><span>{file ? '1 file selected' : 'No file selected'}</span></div>
  </section>
}
function StatCard({ label, value, detail, icon: Icon, tone }) { return <div className={`stat-card stat-${tone}`}><div className="stat-top"><span>{label}</span><span className="stat-icon"><Icon size={17}/></span></div><div className="stat-value">{value}</div><div className="stat-detail">{detail}</div></div> }
function App() {
  const [invoiceFile, setInvoiceFile] = useState(null)
  const [receiptFile, setReceiptFile] = useState(null)
  const [apiKey, setApiKey] = useState('')
  const [showKey, setShowKey] = useState(false)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [result, setResult] = useState(null)
  const [useSample, setUseSample] = useState(false)
  const [expanded, setExpanded] = useState(true)
  const [showConfig, setShowConfig] = useState(false)
  const canRun = (useSample || (invoiceFile && receiptFile)) && !loading
  const runReconciliation = async () => {
    setError('')
    setLoading(true)
    setResult(null)

    const body = new FormData()
    body.append('use_sample', String(useSample))
    if (invoiceFile) body.append('invoice_file', invoiceFile)
    if (receiptFile) body.append('receipt_file', receiptFile)
    if (apiKey.trim()) body.append('api_key', apiKey.trim())

    try {
      let response

      try {
        response = await fetch(`${API_BASE}/api/reconcile`, {
          method: 'POST',
          body,
        })
      } catch (networkError) {
        // fetch rejects before an HTTP response exists for network, CORS,
        // DNS, or connection-refused failures. It cannot identify a Groq-key issue.
        throw new Error(
          `The browser could not connect to ${API_BASE}/api/reconcile. ` +
          `Check that the backend is running on port 8000 and that CORS allows ` +
          `this frontend origin. This error does not by itself indicate a missing Groq API key. ` +
          `Browser detail: ${networkError?.message || 'Network request failed'}`
        )
      }

      const responseText = await response.text()
      let data = {}

      if (responseText) {
        try {
          data = JSON.parse(responseText)
        } catch {
          const preview = responseText.slice(0, 180).replace(/\s+/g, ' ')
          throw new Error(
            `The API returned a non-JSON response (HTTP ${response.status}). ` +
            `Response preview: ${preview || '(empty response)'}. ` +
            `Check the backend logs for the underlying error.`
          )
        }
      }

      if (!response.ok) {
        const detail = typeof data.detail === 'string'
          ? data.detail
          : data.detail
            ? JSON.stringify(data.detail)
            : ''

        if (response.status === 401 || response.status === 403) {
          throw new Error(
            `The API rejected the request (HTTP ${response.status}). ` +
            `${detail || 'Check the API credentials and backend configuration.'}`
          )
        }

        if (response.status === 429) {
          throw new Error(
            `The API or AI provider rate limit was reached (HTTP 429). ` +
            `${detail || 'Wait and try again, or check the Groq account limits.'}`
          )
        }

        throw new Error(
          `The backend returned HTTP ${response.status}. ` +
          `${detail || 'Check the backend terminal for the detailed error.'}`
        )
      }

      if (!data || typeof data !== 'object' || !data.invoice || !data.receipt || !data.summary) {
        throw new Error(
          'The API responded successfully, but the response is missing expected reconciliation fields. ' +
          'Check that the frontend and backend versions match.'
        )
      }

      setResult(data)
    } catch (e) {
      setError(e?.message || 'An unexpected error occurred during reconciliation.')
    } finally {
      setLoading(false)
    }
  }
  const reset = () => { setInvoiceFile(null); setReceiptFile(null); setUseSample(false); setResult(null); setError('') }
  const exportReport = () => { if (!result) return; const blob = new Blob([JSON.stringify(result, null, 2)], {type:'application/json'}); const url = URL.createObjectURL(blob); const a = document.createElement('a'); a.href = url; a.download = 'invoice-reconciliation-report.json'; a.click(); URL.revokeObjectURL(url) }
  return <div className="app-shell">
    <header className="topbar"><div className="topbar-inner"><a className="brand-anchor" href="#top" aria-label="Paras AI Innovations home"><ParasAILogo/></a><div className="header-title"><span>AI OPERATIONS</span><h1>Invoice Reconciliation Hub</h1></div><div className="header-actions"><StatusPill tone="blue"> <Sparkles size={12}/> AI-powered</StatusPill><button className="config-button" onClick={() => setShowConfig(!showConfig)}><KeyRound size={15}/><span>API settings</span><ChevronDown size={14}/></button><div className="avatar">PA</div></div></div></header>
    {showConfig && <div className="config-panel"><div className="config-inner"><div><strong>Groq API key</strong><p>Optional if GROQ_API_KEY is configured on the backend. Your key is sent only to your configured API.</p></div><div className="key-input-wrap"><KeyRound size={16}/><input type={showKey ? 'text' : 'password'} placeholder="gsk_••••••••••••••••" value={apiKey} onChange={e => setApiKey(e.target.value)}/><button onClick={() => setShowKey(!showKey)}>{showKey ? 'Hide' : 'Show'}</button></div><button className="button-secondary" onClick={() => setShowConfig(false)}>Done</button></div></div>}
    <main id="top" className="main-container">
      <div className="page-intro"><div><div className="eyebrow"><span className="eyebrow-line"/> AUTOMATED INVOICE RECONCILIATION <span className="eyebrow-dot">/</span> ACCOUNTS PAYABLE CONTROL</div><h2>Verify every line.<br/><span>Catch every discrepancy.</span></h2><p className="intro-copy">Automatically compare supplier invoices with delivery receipts, identify mismatches, and flag exceptions before payment approval.</p><div className="trust-row"><span><ShieldCheck size={15}/> Invoice-to-receipt validation</span><span><Fingerprint size={15}/> Private by design</span><span><Activity size={15}/> Explainable results</span></div></div><div className="intro-visual"><div className="visual-orbit orbit-one"/><div className="visual-orbit orbit-two"/><div className="visual-center"><Bot size={37}/><span>AI</span></div><div className="floating-doc doc-a"><FileText size={17}/><div><b>Invoice.pdf</b><small>Invoice analysed</small></div><CheckCircle2 size={15}/></div><div className="floating-doc doc-b"><FileCheck2 size={17}/><div><b>Delivery receipt</b><small>Ready to compare</small></div><ArrowRight size={15}/></div><div className="visual-caption"><span className="pulse-dot"/> RECONCILIATION ENGINE <span>v1.0</span></div></div></div>
      <section className="section-block"><div className="section-heading"><div><div className="section-kicker">STEP 01 <span>·</span> TRANSACTION INPUT</div><h2>Upload invoice and receipt</h2><p>Provide both sides of the transaction to start a reliable comparison.</p></div><button className="text-button" onClick={() => {setUseSample(true);setInvoiceFile(null);setReceiptFile(null);setError('')}}><Zap size={15}/> Try sample documents <ArrowRight size={14}/></button></div>
        <div className="upload-grid"><UploadCard title="Vendor invoice" subtitle="The invoice submitted by your supplier." kind="invoice" file={useSample ? {name:'Beverage-Invoice.pdf',size:7140,type:'application/pdf'} : invoiceFile} setFile={f => {setInvoiceFile(f);setUseSample(false);setResult(null)}} disabled={loading}/><UploadCard title="Delivery receipt / GRN" subtitle="Proof of delivery or goods received note." kind="receipt" file={useSample ? {name:'Beverage-GRN.pdf',size:10139,type:'application/pdf'} : receiptFile} setFile={f => {setReceiptFile(f);setUseSample(false);setResult(null)}} disabled={loading}/></div>
        <div className="action-row"><div className="privacy-note"><LockKeyhole size={14}/><span>Files are processed in memory and are not stored by this demo.</span></div><div className="primary-actions">{(invoiceFile || receiptFile || result || useSample) && <button className="button-secondary" onClick={reset} disabled={loading}><RefreshCw size={15}/> Reset</button>}<button className="button-primary" onClick={runReconciliation} disabled={!canRun}>{loading ? <><LoaderCircle className="spin" size={17}/> Analysing documents…</> : <><Sparkles size={16}/> Run AI reconciliation <ArrowRight size={16}/></>}</button></div></div>
        {error && <div className="error-banner"><CircleAlert size={18}/><div><strong>Reconciliation could not be completed</strong><p>{error}</p></div><button className="icon-button" onClick={() => setError('')}><X size={16}/></button></div>}
      </section>
      {loading && <div className="processing-card"><div className="processing-icon"><LoaderCircle size={22} className="spin"/></div><div><strong>Reconciling invoice and receipt</strong><p>The system is comparing transaction details, aligning line items, and checking for discrepancies. This can take a few seconds.</p><div className="processing-track"><span/></div></div><span className="processing-label">IN PROGRESS</span></div>}
      {result && <section className="results-section"><div className="section-heading results-heading"><div><div className="section-kicker">STEP 03 <span>·</span> VERIFICATION OUTPUT</div><h2>Reconciliation results</h2><p>Review extracted values and focus on the exceptions that need attention.</p></div><button className="button-secondary" onClick={exportReport}><ArrowDownToLine size={15}/> Export report</button></div>
        <div className="result-banner"><div className={`result-banner-icon ${result.summary.isClean ? 'clean' : 'attention'}`}>{result.summary.isClean ? <BadgeCheck size={22}/> : <CircleAlert size={22}/>}</div><div className="result-banner-copy"><strong>{result.summary.isClean ? 'All checks passed' : `${result.summary.discrepancies} exception${result.summary.discrepancies === 1 ? '' : 's'} need review`}</strong><p>{result.summary.isClean ? 'No discrepancies were found between the invoice and delivery receipt.' : 'Review flagged fields before approving this transaction for payment.'}</p></div><StatusPill tone={result.summary.isClean ? 'green' : 'red'}>{result.summary.isClean ? 'Verified' : 'Action required'}</StatusPill></div>
        <div className="stats-grid"><StatCard label="Fields / items compared" value={result.summary.productsCompared} detail="Across both documents" icon={FileCheck2} tone="blue"/><StatCard label="Matched items" value={result.summary.matched} detail="No difference detected" icon={CheckCircle2} tone="green"/><StatCard label="Discrepancies" value={result.summary.discrepancies} detail={result.summary.discrepancies ? 'Requires investigation' : 'No exceptions found'} icon={CircleAlert} tone={result.summary.discrepancies ? 'red' : 'green'}/><StatCard label="Match rate" value={`${result.summary.confidence}%`} detail="Matched items / compared" icon={Gauge} tone="violet"/></div>
        <div className="panel exceptions-panel"><button className="exceptions-toggle" onClick={() => setExpanded(!expanded)}><div className="exceptions-heading-icon"><CircleAlert size={18}/></div><div className="exceptions-heading-copy"><h3>Discrepancy report</h3><p>Actionable exceptions detected by the reconciliation engine.</p></div><span className={`exception-count ${result.discrepancies.length ? 'has-issues' : ''}`}>{result.discrepancies.length} found</span><ChevronDown className={expanded ? 'chevron-open' : ''} size={18}/></button>{expanded && <div className="exception-list">{result.discrepancies.length ? result.discrepancies.map((item,i)=><div className="exception-item" key={`${item.product}-${i}`}><div className={`exception-marker ${item.status === 'missing' ? 'red' : 'amber'}`}>{item.status === 'missing' ? <X size={14}/> : <Info size={14}/>}</div><div className="exception-content"><div className="exception-title-row"><strong>{item.product}</strong><StatusPill tone={item.status === 'missing' ? 'red' : 'amber'}>{item.status === 'missing' ? 'Missing / unmatched' : 'Value discrepancy'}</StatusPill></div><p>{item.message}</p></div></div>) : <div className="all-clear"><CheckCircle2 size={19}/><div><strong>No discrepancies detected</strong><p>All compared line items passed the current reconciliation rules.</p></div></div>}{result.matchedProducts?.length > 0 && <div className="matched-list"><div className="matched-list-title"><CheckCircle2 size={15}/> Matched products <span>{result.matchedProducts.length}</span></div><div className="matched-chips">{result.matchedProducts.map(p=><span key={p}><Check size={12}/>{p}</span>)}</div></div>}</div>}</div>
      </section>}
      <footer className="footer"><div className="footer-brand"><ParasAILogo/><span className="footer-divider"/><span>Automated Invoice Reconciliation</span></div><div className="footer-right"><span><span className="footer-status-dot"/> API-connected workflow</span><span>Built by Paras AI Innovations</span></div></footer>
    </main>
  </div>
}

createRoot(document.getElementById('root')).render(<React.StrictMode><App/></React.StrictMode>)
