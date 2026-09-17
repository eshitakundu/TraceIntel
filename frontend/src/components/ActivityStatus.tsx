import { useEffect, useState } from "react";

export default function ActivityStatus({
  title,
  description,
}: {
  title: string;
  description: string;
}) {
  const [elapsed, setElapsed] = useState(0);
  useEffect(() => {
    const started = Date.now();
    const timer = setInterval(
      () => setElapsed(Math.floor((Date.now() - started) / 1000)),
      1000,
    );
    return () => clearInterval(timer);
  }, []);
  return (
    <div className="activity-status">
      <span className="activity-spinner" aria-hidden="true" />
      <div role="status" aria-live="polite">
        <strong>{title}</strong>
        <p>{description}</p>
      </div>
      <span
        className="activity-elapsed"
        aria-label={elapsed + " seconds elapsed"}
      >
        {elapsed}s
      </span>
    </div>
  );
}
