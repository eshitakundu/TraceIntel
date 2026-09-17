import { useHealth } from '../hooks/useHealth'

export default function Home() {
  const { state, retry } = useHealth()
  return <>
    <div className="eyebrow"><span className="dot" /> EVM TRANSACTION INTELLIGENCE</div>
    <section className="hero"><div><h1>Follow the transaction.<br /><span>Understand the evidence.</span></h1>
      <p>On-chain facts, deterministic risk signals, and traceable interpretation. Built to make complex transactions understandable.</p></div>
      <aside className="status-card"><span className="label">SYSTEM STATUS</span><strong className={state}>{state === 'online' ? 'API connected' : state === 'checking' ? 'Checking connection…' : 'API unavailable'}</strong><small>Live health check · FastAPI</small>{state === 'offline' && <button onClick={retry}>Retry connection</button>}</aside>
    </section>
    <section className="panel"><div className="section-heading"><h2>Transaction workspace</h2><span className="badge">FOUNDATION</span></div>
      <p>The application foundation is running. Transaction analysis will become available as the evidence pipeline is implemented.</p>
      <div className="network-row"><span>01 / Ethereum</span><span>02 / Monad</span><small>Planned networks · read-only analysis</small></div>
    </section>
    <section><div className="section-heading"><h2>From transaction to understanding</h2><span className="label">THE PIPELINE</span></div>
      <div className="pipeline">{['Acquire', 'Decode', 'Evidence', 'Rules', 'Interpret', 'Report'].map((label, index) => <div key={label}><small>0{index + 1}</small><strong>{label}</strong></div>)}</div></section>
    <div className="principles"><article><h3>Facts stay facts</h3><p>Blockchain evidence and numerical risk scores belong to deterministic Python code.</p></article><article><h3>Every claim has a source</h3><p>Interpretations will reference evidence IDs, keeping their reasoning traceable.</p></article><article><h3>Unknown stays visible</h3><p>Missing provider data is a coverage limitation, never evidence of safety.</p></article></div>
  </>
}