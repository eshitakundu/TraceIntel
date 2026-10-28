const DRIVE_ID = "1-5eEX6gudDaP5FLFxx9WotcHQ9CJlThD";
const DRIVE_URL = `https://drive.google.com/file/d/${DRIVE_ID}/view`;
const EMBED_URL = `https://drive.google.com/file/d/${DRIVE_ID}/preview`;

export default function DemoWalkthrough() {
  return (
    <section
      className="walkthrough"
      id="walkthrough"
      aria-labelledby="walkthrough-title"
    >
      <div className="walkthrough-copy">
        <span className="walkthrough-label">Recorded walkthrough · 1:44</span>
        <h2 id="walkthrough-title">
          Watch a permission
          <br />
          <span className="dim">become a decision.</span>
        </h2>
        <p>
          Follow a real transaction from its original approval to today&apos;s
          allowance, spender changes and cited revoke advice.
        </p>
        <dl className="walkthrough-proof">
          <div>
            <dt>Then</dt>
            <dd>Decode the approval</dd>
          </div>
          <div>
            <dt>Now</dt>
            <dd>Check live exposure</dd>
          </div>
          <div>
            <dt>Decision</dt>
            <dd>Explain what to do</dd>
          </div>
        </dl>
        <div className="walkthrough-actions">
          <a href={DRIVE_URL} target="_blank" rel="noreferrer">
            Open in Drive
          </a>
        </div>
      </div>

      <div className="walkthrough-screen">
        <iframe
          src={EMBED_URL}
          title="TraceIntel recorded product walkthrough"
          loading="lazy"
          referrerPolicy="strict-origin-when-cross-origin"
          allow="autoplay; fullscreen"
          allowFullScreen
        />
      </div>
    </section>
  );
}
