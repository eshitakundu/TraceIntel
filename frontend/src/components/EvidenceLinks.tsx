export default function EvidenceLinks({ ids }: { ids: string[] }) {
  return (
    <span className="evidence-links">
      {ids.map((id, index) => (
        <a
          key={id}
          href={"#evidence-" + encodeURIComponent(id)}
          aria-label={"View evidence " + id}
        >
          [{index + 1}]
        </a>
      ))}
    </span>
  );
}
